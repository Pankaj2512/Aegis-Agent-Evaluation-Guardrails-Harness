"""Dedicated worker loop for pending workflow runs."""

from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from app.config import settings
from app.db import models
from app.db.database import SessionLocal
from app.services.executor import active_run_count, schedule_run

logger = logging.getLogger("aegis.run_worker")

_worker_task: asyncio.Task[None] | None = None


def claim_pending_runs(limit: int = 5) -> list[UUID]:
    db = SessionLocal()
    try:
        if active_run_count() >= settings.max_concurrent_runs:
            return []
        slots = max(0, settings.max_concurrent_runs - active_run_count())
        rows = (
            db.query(models.WorkflowRun)
            .filter(models.WorkflowRun.status.in_(["pending", "queued"]))
            .order_by(models.WorkflowRun.created_at.asc())
            .with_for_update(skip_locked=True)
            .limit(min(limit, slots))
            .all()
        )
        run_ids: list[UUID] = []
        for row in rows:
            row.status = "queued"
            run_ids.append(row.id)
        if run_ids:
            db.commit()
        return run_ids
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def _worker_loop() -> None:
    while True:
        try:
            # claim_pending_runs issues a blocking SELECT … FOR UPDATE + commit;
            # run it off the event loop so the poll tick never stalls the app
            # process's async work (audit P2-21).
            run_ids = await asyncio.to_thread(claim_pending_runs)
            for run_id in run_ids:
                schedule_run(run_id)
        except Exception:
            logger.exception("Run worker tick failed")
        await asyncio.sleep(max(1, int(getattr(settings, "run_worker_poll_seconds", 2) or 2)))


def start_run_worker() -> None:
    global _worker_task
    if getattr(settings, "run_execution_mode", "inline") != "worker":
        return
    if _worker_task and not _worker_task.done():
        return
    _worker_task = asyncio.create_task(_worker_loop())
    logger.info("Run worker started")


async def stop_run_worker() -> None:
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    _worker_task = None


def run_worker_status() -> dict[str, object]:
    running = _worker_task is not None and not _worker_task.done()
    return {
        "mode": getattr(settings, "run_execution_mode", "inline"),
        "running": running,
        "poll_seconds": int(getattr(settings, "run_worker_poll_seconds", 2) or 2),
    }