"""Background job status API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.auth.deps import get_current_user_id
from app.db.database import get_db
from app.services.job_queue import get_job
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}")
def job_status(
    job_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    job = get_job(db, job_id, user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": str(job.id),
        "job_type": job.job_type,
        "status": job.status,
        "workflow_id": str(job.workflow_id) if job.workflow_id else None,
        "payload": job.payload_json,
        "result": job.result_json,
        "error": job.error,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
    }