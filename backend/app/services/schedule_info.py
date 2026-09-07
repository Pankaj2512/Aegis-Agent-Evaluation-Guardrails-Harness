"""Schedule metadata for workflows (next fire, last scheduled run)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import models
from app.services.cron_utils import cron_is_valid, cron_next_runs
from app.services.schedule_worker import _trigger_schedule


def is_scheduled_run_input(input_text: str | None) -> bool:
    if not input_text:
        return False
    try:
        payload = json.loads(input_text)
    except json.JSONDecodeError:
        return False
    return isinstance(payload, dict) and payload.get("scheduled") is True


def last_scheduled_run_at(db: Session, workflow_id: UUID) -> datetime | None:
    rows = (
        db.query(models.WorkflowRun.created_at, models.WorkflowRun.input_text)
        .join(models.WorkflowVersion)
        .filter(models.WorkflowVersion.workflow_id == workflow_id)
        .order_by(models.WorkflowRun.created_at.desc())
        .limit(50)
        .all()
    )
    for created_at, input_text in rows:
        if is_scheduled_run_input(input_text):
            return created_at
    return None


def schedule_info_for_graph(
    workflow_id: UUID,
    workflow_name: str,
    graph_json: dict,
    *,
    last_fired_at: datetime | None = None,
) -> dict[str, Any] | None:
    cron_expr, _ = _trigger_schedule(graph_json)
    if not cron_expr:
        return None

    valid = cron_is_valid(cron_expr)
    next_runs = cron_next_runs(cron_expr, count=3) if valid else []

    return {
        "workflow_id": str(workflow_id),
        "workflow_name": workflow_name,
        "cron": cron_expr,
        "cron_valid": valid,
        "next_run_at": next_runs[0].isoformat() if next_runs else None,
        "next_runs": [dt.isoformat() for dt in next_runs],
        "last_fired_at": last_fired_at.isoformat() if last_fired_at else None,
    }


def batch_last_scheduled_run_at(
    db: Session,
    workflow_ids: list[UUID],
) -> dict[UUID, datetime]:
    if not workflow_ids:
        return {}
    rows = (
        db.query(
            models.WorkflowVersion.workflow_id,
            models.WorkflowRun.created_at,
            models.WorkflowRun.input_text,
        )
        .join(models.WorkflowRun, models.WorkflowRun.workflow_version_id == models.WorkflowVersion.id)
        .filter(models.WorkflowVersion.workflow_id.in_(workflow_ids))
        .order_by(models.WorkflowVersion.workflow_id, models.WorkflowRun.created_at.desc())
        .all()
    )
    result: dict[UUID, datetime] = {}
    for workflow_id, created_at, input_text in rows:
        if workflow_id in result:
            continue
        if is_scheduled_run_input(input_text):
            result[workflow_id] = created_at
    return result


def list_user_scheduled_workflows(db: Session, user_id: UUID) -> list[dict[str, Any]]:
    rows = (
        db.query(models.WorkflowSchedule, models.Workflow, models.WorkflowVersion)
        .join(models.Workflow, models.Workflow.id == models.WorkflowSchedule.workflow_id)
        .join(
            models.WorkflowVersion,
            models.WorkflowVersion.id == models.WorkflowSchedule.workflow_version_id,
        )
        .filter(models.Workflow.user_id == user_id, models.WorkflowSchedule.enabled.is_(True))
        .all()
    )
    workflow_ids = [workflow.id for _schedule, workflow, _version in rows]
    last_fired_map = batch_last_scheduled_run_at(db, workflow_ids)
    items: list[dict[str, Any]] = []
    for schedule, workflow, version in rows:
        last_fired = last_fired_map.get(workflow.id)
        info = schedule_info_for_graph(
            workflow.id,
            workflow.name,
            version.graph_json,
            last_fired_at=last_fired,
        )
        if info:
            info["cron_valid"] = schedule.cron_valid
            info["cron"] = schedule.cron_expr
            items.append(info)
    items.sort(key=lambda row: row.get("next_run_at") or "")
    return items