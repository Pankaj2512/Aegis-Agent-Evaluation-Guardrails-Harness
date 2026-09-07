"""Backfill observability rollups from historical workflow runs."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.db import models
from app.db.database import SessionLocal
from app.services.observability_rollups import record_run_rollup


def reset_rollups_for_user(db: Session, user_id: UUID) -> int:
    deleted = (
        db.query(models.ObservabilityRollup)
        .filter(models.ObservabilityRollup.user_id == user_id)
        .delete(synchronize_session=False)
    )
    return int(deleted or 0)


def backfill_rollups_for_user(user_id: UUID | None, *, limit: int = 5000) -> int:
    db = SessionLocal()
    updated = 0
    try:
        if user_id is not None:
            reset_rollups_for_user(db, user_id)

        query = (
            db.query(models.WorkflowRun)
            .options(
                joinedload(models.WorkflowRun.version).joinedload(models.WorkflowVersion.workflow)
            )
            .join(models.WorkflowVersion)
            .join(models.Workflow)
            .filter(models.WorkflowRun.status.in_(["completed", "failed", "cancelled"]))
            .order_by(models.WorkflowRun.created_at.asc())
            .limit(limit)
        )
        if user_id is not None:
            query = query.filter(models.Workflow.user_id == user_id)

        for run in query.all():
            workflow = run.version.workflow if run.version else None
            if not workflow:
                continue
            record_run_rollup(
                db,
                user_id=workflow.user_id,
                workflow_id=workflow.id,
                status=run.status,
                metrics=run.metrics_json,
                occurred_at=run.completed_at or run.created_at,
            )
            updated += 1
        db.commit()
        return updated
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()