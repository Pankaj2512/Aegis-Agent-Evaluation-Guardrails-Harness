"""Eval regression detection and notifications."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.db import models
from app.services.quality_metrics import detect_eval_regression
from app.services.observability_events import broadcast_observability_event

logger = logging.getLogger("aegis.regression")


def _recent_eval_trend(
    db,
    workflow_id,
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    from app.db.database import SessionLocal

    session = db or SessionLocal()
    close_session = db is None
    try:
        rows = (
            session.query(models.WorkflowRun)
            .join(models.WorkflowVersion)
            .filter(models.WorkflowVersion.workflow_id == workflow_id)
            .order_by(models.WorkflowRun.created_at.desc())
            .limit(limit)
            .all()
        )
        trend: list[dict[str, Any]] = []
        for row in rows:
            metrics = row.metrics_json or {}
            aggregate = metrics.get("eval_aggregate")
            if aggregate is None:
                continue
            trend.append(
                {
                    "run_id": str(row.id),
                    "created_at": row.created_at.isoformat() if row.created_at else "",
                    "aggregate": float(aggregate),
                    "passed": metrics.get("eval_passed"),
                }
            )
        return list(reversed(trend))
    finally:
        if close_session:
            session.close()


async def maybe_emit_eval_regression(
    run: models.WorkflowRun,
    workflow: models.Workflow | None,
    db=None,
) -> dict[str, Any] | None:
    if not workflow or not run.metrics_json:
        return None
    aggregate = run.metrics_json.get("eval_aggregate")
    if aggregate is None:
        return None

    # _recent_eval_trend runs a sync joined trend query; it executes after
    # every completed run, so keep it off the event loop (audit P2-22). It is
    # awaited (never concurrent), so reusing the caller's Session is safe.
    trend = await asyncio.to_thread(_recent_eval_trend, db, workflow.id)
    regression = detect_eval_regression(trend)
    if not regression:
        return None

    payload = {
        "type": "eval_regression",
        "run_id": str(run.id),
        "workflow_id": str(workflow.id),
        "workflow_name": workflow.name,
        "regression": regression,
    }
    try:
        await broadcast_observability_event(str(workflow.user_id), payload)
    except Exception:
        logger.exception("Failed to broadcast eval regression", extra={"run_id": str(run.id)})

    webhook_url = workflow.webhook_url
    if webhook_url:
        from app.services.webhook import dispatch_webhook

        from app.services.async_tasks import schedule_task

        schedule_task(
            dispatch_webhook(
                webhook_url,
                {
                    "event": "eval_regression",
                    "run_id": str(run.id),
                    "workflow_id": str(workflow.id),
                    "workflow_name": workflow.name,
                    **regression,
                },
            )
        )
    return regression