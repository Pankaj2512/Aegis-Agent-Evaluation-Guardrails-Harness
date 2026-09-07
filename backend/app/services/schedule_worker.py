"""Background cron scheduler for workflow Trigger nodes (n8n Schedule Trigger)."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from croniter import croniter
from app.config import settings
from app.db import models
from app.db.database import SessionLocal
from app.services.executor import active_run_count, schedule_run
from app.services.graph_validation import GraphValidationError, validate_workflow_graph

logger = logging.getLogger("aegis.scheduler")

_scheduler_task: asyncio.Task[None] | None = None
_last_retention_at: datetime | None = None


def cron_matches_now(cron_expr: str, now: datetime | None = None) -> bool:
    moment = (now or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
    try:
        itr = croniter(cron_expr.strip(), moment - timedelta(minutes=1))
        next_fire = itr.get_next(datetime).replace(second=0, microsecond=0)
        return next_fire == moment
    except (ValueError, KeyError):
        return False


def should_fire_schedule(workflow_id: str, minute_key: str, fired: dict[str, str]) -> bool:
    """In-memory dedup helper (tests); production uses DB-backed last_fired_at."""
    if fired.get(workflow_id) == minute_key:
        return False
    fired[workflow_id] = minute_key
    return True


def _claim_schedule_fire(db, schedule_id: UUID, minute_key: str) -> bool:
    schedule = (
        db.query(models.WorkflowSchedule)
        .filter(models.WorkflowSchedule.id == schedule_id)
        .with_for_update(skip_locked=True)
        .first()
    )
    if not schedule:
        return False
    window_start = datetime.strptime(minute_key, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    last = schedule.last_fired_at
    if last is not None and last.tzinfo is None:
        # DB-loaded datetimes may be naive; normalize to aware UTC.
        last = last.replace(tzinfo=timezone.utc)
    if last and last >= window_start:
        return False
    schedule.last_fired_at = window_start
    db.commit()
    return True


def _try_claim_schedule(schedule_id: UUID, minute_key: str) -> bool:
    db = SessionLocal()
    try:
        return _claim_schedule_fire(db, schedule_id, minute_key)
    finally:
        db.close()


def _trigger_schedule(graph_json: dict) -> tuple[str | None, str | None]:
    for node in graph_json.get("nodes", []):
        data = node.get("data") or {}
        if data.get("nodeType") != "trigger":
            continue
        if data.get("triggerType") != "schedule":
            return None, None
        return data.get("scheduleCron"), node.get("id")
    return None, None


def _scan_scheduled_workflows() -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = (
            db.query(models.WorkflowSchedule, models.Workflow, models.WorkflowVersion)
            .join(models.Workflow, models.Workflow.id == models.WorkflowSchedule.workflow_id)
            .join(
                models.WorkflowVersion,
                models.WorkflowVersion.id == models.WorkflowSchedule.workflow_version_id,
            )
            .filter(
                models.WorkflowSchedule.enabled.is_(True),
                models.WorkflowSchedule.cron_valid.is_(True),
            )
            .all()
        )

        due: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        minute_key = now.strftime("%Y-%m-%dT%H:%M")

        for schedule, workflow, version in rows:
            if not cron_matches_now(schedule.cron_expr, now):
                continue
            try:
                validate_workflow_graph(version.graph_json)
            except GraphValidationError:
                continue
            from app.services.budgets import check_workflow_budget

            breach = check_workflow_budget(db, workflow)
            if breach:
                logger.warning(
                    "Skipping scheduled fire — budget breached",
                    extra={"workflow_id": str(workflow.id), "reason": breach},
                )
                continue
            if not _try_claim_schedule(schedule.id, minute_key):
                continue
            due.append(
                {
                    "workflow_id": workflow.id,
                    "version_id": version.id,
                    "user_id": workflow.user_id,
                }
            )
        return due
    finally:
        db.close()


def _create_scheduled_run_row(workflow_id: UUID, version_id: UUID) -> UUID | None:
    """Insert the pending run row (blocking DB work — safe to run in a worker
    thread). Returns the run id to schedule on the event loop, or None when the
    run should not be started here (concurrency cap reached, or worker mode where
    a separate process claims it).

    Scheduling itself (asyncio.create_task via schedule_run) must NOT happen in
    this thread: it requires a running event loop, and doing it here raised
    "no running event loop", stranding every scheduled run as pending forever.
    The caller runs schedule_run on the loop instead.
    """
    if active_run_count() >= settings.max_concurrent_runs:
        logger.warning(
            "Skipping scheduled run — max concurrent runs reached",
            extra={"workflow_id": str(workflow_id), "event": "schedule_skipped"},
        )
        return None
    db = SessionLocal()
    try:
        run = models.WorkflowRun(
            workflow_version_id=version_id,
            status="pending",
            input_text=json.dumps({"scheduled": True, "trigger": "cron"}),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        if settings.run_execution_mode == "worker":
            return None
        return run.id
    finally:
        db.close()


def _maybe_run_retention() -> None:
    global _last_retention_at
    if not settings.retention_enabled:
        return
    now = datetime.now(timezone.utc)
    if _last_retention_at and (now - _last_retention_at).total_seconds() < 86_400:
        return
    from app.services.retention import purge_old_runs

    deleted = purge_old_runs()
    _last_retention_at = now
    if deleted:
        logger.info("Retention purge completed", extra={"deleted_runs": deleted, "event": "retention_purge"})


def _evaluate_alerts() -> None:
    from app.services.alerts import evaluate_alert_rules

    db = SessionLocal()
    try:
        evaluate_alert_rules(db)
    finally:
        db.close()


def _sweep_stale_runs() -> None:
    """Reap runs left pending/running past the staleness window. Complements
    startup.recover_stale_runs for processes that stay up for days, where a
    scheduled fire that never progresses would otherwise pile up and (before the
    gate fix) wedge run creation with 429s."""
    from app.services.run_concurrency import sweep_stale_runs

    db = SessionLocal()
    try:
        sweep_stale_runs(db)
    finally:
        db.close()


async def _scheduler_loop() -> None:
    while True:
        try:
            if settings.schedule_enabled:
                due = await asyncio.to_thread(_scan_scheduled_workflows)
                for item in due:
                    # DB insert in a worker thread; schedule_run on the event loop
                    # (it calls asyncio.create_task, which needs a running loop).
                    run_id = await asyncio.to_thread(
                        _create_scheduled_run_row, item["workflow_id"], item["version_id"]
                    )
                    if run_id is not None:
                        schedule_run(run_id)
                        logger.info(
                            "Scheduled run created",
                            extra={
                                "workflow_id": str(item["workflow_id"]),
                                "run_id": str(run_id),
                                "event": "schedule_fired",
                            },
                        )
            await asyncio.to_thread(_sweep_stale_runs)
            await asyncio.to_thread(_evaluate_alerts)
            await asyncio.to_thread(_maybe_run_retention)
        except Exception:
            logger.exception("Scheduler tick failed")
        await asyncio.sleep(max(15, settings.schedule_poll_seconds))


def start_schedule_worker() -> None:
    global _scheduler_task
    if not settings.schedule_enabled:
        return
    if _scheduler_task and not _scheduler_task.done():
        return
    _scheduler_task = asyncio.create_task(_scheduler_loop())
    logger.info("Schedule worker started", extra={"poll_seconds": settings.schedule_poll_seconds})


async def stop_schedule_worker() -> None:
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
    _scheduler_task = None


def scheduler_status() -> dict[str, object]:
    running = _scheduler_task is not None and not _scheduler_task.done()
    return {
        "enabled": settings.schedule_enabled,
        "running": running,
        "poll_seconds": settings.schedule_poll_seconds,
        "last_fired_workflows": None,
    }


def count_scheduled_workflows(graphs: list[dict]) -> int:
    total = 0
    for graph in graphs:
        cron, _ = _trigger_schedule(graph)
        if cron:
            total += 1
    return total