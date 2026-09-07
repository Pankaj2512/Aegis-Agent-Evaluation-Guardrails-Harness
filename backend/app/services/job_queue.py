"""Database-backed background job queue."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.db import models
from app.db.database import SessionLocal

logger = logging.getLogger("aegis.jobs")

JOB_TYPES = frozenset(
    {
        "knowledge_bulk_import",
        "knowledge_reindex",
        "rollup_backfill",
        "run_retention",
    }
)


def create_job(
    db: Session,
    *,
    job_type: str,
    user_id: UUID | None = None,
    workflow_id: UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> models.BackgroundJob:
    if job_type not in JOB_TYPES:
        raise ValueError(f"Unsupported job type: {job_type}")
    row = models.BackgroundJob(
        id=uuid4(),
        job_type=job_type,
        status="queued",
        user_id=user_id,
        workflow_id=workflow_id,
        payload_json=payload or {},
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_job(db: Session, job_id: UUID, user_id: UUID | None = None) -> models.BackgroundJob | None:
    query = db.query(models.BackgroundJob).filter(models.BackgroundJob.id == job_id)
    if user_id is not None:
        query = query.filter(models.BackgroundJob.user_id == user_id)
    return query.first()


def mark_job_running(db: Session, job: models.BackgroundJob) -> None:
    job.status = "running"
    job.started_at = datetime.now(timezone.utc)
    db.commit()


def mark_job_completed(
    db: Session,
    job: models.BackgroundJob,
    *,
    result: dict[str, Any] | None = None,
) -> None:
    job.status = "completed"
    job.result_json = result or {}
    job.completed_at = datetime.now(timezone.utc)
    job.error = None
    db.commit()


def mark_job_failed(db: Session, job: models.BackgroundJob, error: str) -> None:
    job.status = "failed"
    job.error = error[:2000]
    job.completed_at = datetime.now(timezone.utc)
    db.commit()


async def dispatch_job(job_id: UUID) -> None:
    """Execute a queued job (called from FastAPI background task or worker loop)."""
    db = SessionLocal()
    try:
        job = (
            db.query(models.BackgroundJob)
            .filter(
                models.BackgroundJob.id == job_id,
                models.BackgroundJob.status == "queued",
            )
            .with_for_update(skip_locked=True)
            .first()
        )
        if not job:
            return
        mark_job_running(db, job)

        if job.job_type == "knowledge_bulk_import":
            from app.services.knowledge_jobs import run_bulk_import_job

            documents = (job.payload_json or {}).get("documents") or []
            count = await asyncio.to_thread(run_bulk_import_job, job.workflow_id, documents)
            mark_job_completed(db, job, result={"count": count})
        elif job.job_type == "knowledge_reindex":
            from app.services.knowledge_jobs import run_reindex_job

            count = await asyncio.to_thread(run_reindex_job, job.workflow_id)
            mark_job_completed(db, job, result={"count": count})
        elif job.job_type == "rollup_backfill":
            from app.services.rollup_backfill import backfill_rollups_for_user

            count = await asyncio.to_thread(backfill_rollups_for_user, job.user_id)
            mark_job_completed(db, job, result={"buckets_updated": count})
        elif job.job_type == "run_retention":
            from app.services.retention import purge_old_runs

            count = await asyncio.to_thread(purge_old_runs)
            mark_job_completed(db, job, result={"deleted_runs": count})
        else:
            mark_job_failed(db, job, f"Unhandled job type: {job.job_type}")
    except Exception as exc:
        logger.exception("Job failed", extra={"job_id": str(job_id)})
        # Prefer the live session; if it is dead after a DB error, open a fresh
        # one so the job is not left stuck in `running` until process restart.
        try:
            if db.is_active:
                job = (
                    db.query(models.BackgroundJob)
                    .filter(models.BackgroundJob.id == job_id)
                    .first()
                )
                if job:
                    mark_job_failed(db, job, str(exc))
            else:
                raise RuntimeError("session inactive")
        except Exception:  # noqa: BLE001
            recovery = SessionLocal()
            try:
                job = (
                    recovery.query(models.BackgroundJob)
                    .filter(models.BackgroundJob.id == job_id)
                    .first()
                )
                if job and job.status in ("running", "queued"):
                    mark_job_failed(recovery, job, str(exc))
            except Exception:  # noqa: BLE001
                logger.exception(
                    "Failed to mark job failed after error",
                    extra={"job_id": str(job_id)},
                )
            finally:
                recovery.close()
    finally:
        db.close()