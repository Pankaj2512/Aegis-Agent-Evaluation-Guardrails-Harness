"""Human feedback on runs: thumbs + comment, feeding golden datasets."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user_id
from app.db import models
from app.db.database import get_db

router = APIRouter(prefix="/api/feedback", tags=["feedback"])


class FeedbackCreate(BaseModel):
    run_id: UUID
    node_id: str | None = None
    rating: int = Field(ge=-1, le=1)
    comment: str | None = Field(default=None, max_length=2000)


@router.post("", status_code=201)
def create_feedback(
    payload: FeedbackCreate,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    if payload.rating == 0:
        raise HTTPException(status_code=400, detail="rating must be +1 or -1")
    run = (
        db.query(models.WorkflowRun)
        .join(
            models.WorkflowVersion,
            models.WorkflowRun.workflow_version_id == models.WorkflowVersion.id,
        )
        .join(models.Workflow, models.WorkflowVersion.workflow_id == models.Workflow.id)
        .filter(
            models.WorkflowRun.id == payload.run_id,
            models.Workflow.user_id == user_id,
        )
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    fb = models.Feedback(
        user_id=user_id,
        run_id=payload.run_id,
        node_id=payload.node_id,
        rating=payload.rating,
        comment=payload.comment,
    )
    db.add(fb)
    db.commit()
    return {"id": str(fb.id)}


@router.get("/run/{run_id}")
def list_run_feedback(
    run_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    rows = (
        db.query(models.Feedback)
        .filter(models.Feedback.run_id == run_id, models.Feedback.user_id == user_id)
        .order_by(models.Feedback.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(f.id),
            "node_id": f.node_id,
            "rating": f.rating,
            "comment": f.comment,
            "created_at": f.created_at.isoformat() if f.created_at else None,
        }
        for f in rows
    ]
