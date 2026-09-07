"""Keep workflow_schedules index in sync with canvas graphs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db import models
from app.services.cron_utils import cron_is_valid
from app.services.schedule_worker import _trigger_schedule


def sync_workflow_schedule(
    db: Session,
    *,
    workflow_id: UUID,
    version_id: UUID,
    graph_json: dict,
) -> None:
    cron_expr, trigger_node_id = _trigger_schedule(graph_json)

    existing = (
        db.query(models.WorkflowSchedule)
        .filter(models.WorkflowSchedule.workflow_id == workflow_id)
        .first()
    )

    if not cron_expr:
        if existing:
            db.delete(existing)
        return

    cron_valid = cron_is_valid(cron_expr)
    payload = {
        "workflow_version_id": version_id,
        "cron_expr": cron_expr.strip(),
        "trigger_node_id": trigger_node_id,
        "enabled": True,
        "cron_valid": cron_valid,
    }

    if existing:
        for key, value in payload.items():
            setattr(existing, key, value)
        return

    db.add(
        models.WorkflowSchedule(
            workflow_id=workflow_id,
            **payload,
        )
    )