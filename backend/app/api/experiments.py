"""Experiments: batch dataset runs and version regression gates."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user_id
from app.db import models
from app.db.database import get_db
from app.services.async_tasks import schedule_task
from app.services.experiment_runner import DEFAULT_MAX_EVAL_DROP, run_experiment

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


class ExperimentCreate(BaseModel):
    workflow_id: UUID
    dataset_id: UUID
    version_id: UUID
    kind: str = "batch"  # batch | regression
    baseline_version_id: UUID | None = None
    max_eval_drop: float | None = None


def _serialize(exp: models.Experiment) -> dict:
    return {
        "id": str(exp.id),
        "workflow_id": str(exp.workflow_id),
        "dataset_id": str(exp.dataset_id),
        "kind": exp.kind,
        "version_id": str(exp.version_id),
        "baseline_version_id": str(exp.baseline_version_id) if exp.baseline_version_id else None,
        "status": exp.status,
        "summary": exp.summary_json,
        "created_at": exp.created_at.isoformat() if exp.created_at else None,
        "completed_at": exp.completed_at.isoformat() if exp.completed_at else None,
    }


def _check_version(db: Session, version_id: UUID, workflow_id: UUID) -> None:
    version = (
        db.query(models.WorkflowVersion)
        .filter(
            models.WorkflowVersion.id == version_id,
            models.WorkflowVersion.workflow_id == workflow_id,
        )
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail=f"Version {version_id} not found")


@router.get("")
def list_experiments(
    workflow_id: UUID | None = None,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    query = db.query(models.Experiment).filter(models.Experiment.user_id == user_id)
    if workflow_id:
        query = query.filter(models.Experiment.workflow_id == workflow_id)
    return [
        _serialize(e)
        for e in query.order_by(models.Experiment.created_at.desc()).limit(50).all()
    ]


@router.post("", status_code=201)
async def create_experiment(
    payload: ExperimentCreate,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    workflow = (
        db.query(models.Workflow)
        .filter(models.Workflow.id == payload.workflow_id, models.Workflow.user_id == user_id)
        .first()
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    dataset = (
        db.query(models.Dataset)
        .filter(models.Dataset.id == payload.dataset_id, models.Dataset.user_id == user_id)
        .first()
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    item_count = (
        db.query(models.DatasetItem).filter(models.DatasetItem.dataset_id == dataset.id).count()
    )
    if item_count == 0:
        raise HTTPException(status_code=400, detail="Dataset has no items")

    _check_version(db, payload.version_id, payload.workflow_id)
    if payload.kind == "regression":
        if not payload.baseline_version_id:
            raise HTTPException(status_code=400, detail="Regression requires baseline_version_id")
        _check_version(db, payload.baseline_version_id, payload.workflow_id)
    elif payload.kind != "batch":
        raise HTTPException(status_code=400, detail="kind must be batch or regression")

    exp = models.Experiment(
        user_id=user_id,
        workflow_id=payload.workflow_id,
        dataset_id=payload.dataset_id,
        kind=payload.kind,
        version_id=payload.version_id,
        baseline_version_id=payload.baseline_version_id,
        status="pending",
        # Options ride in summary_json until the runner overwrites it.
        summary_json={"max_eval_drop": payload.max_eval_drop or DEFAULT_MAX_EVAL_DROP}
        if payload.kind == "regression"
        else None,
    )
    db.add(exp)
    db.commit()
    schedule_task(run_experiment(exp.id))
    return _serialize(exp)


@router.get("/{experiment_id}")
def get_experiment(
    experiment_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    exp = (
        db.query(models.Experiment)
        .filter(models.Experiment.id == experiment_id, models.Experiment.user_id == user_id)
        .first()
    )
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return _serialize(exp)


@router.get("/{experiment_id}/gate")
def experiment_gate(
    experiment_id: UUID,
    strict: bool = Query(
        False,
        description="When true, respond 409 if the gate is not passed (failed/pending/error) "
        "so a CI step can fail on it directly (curl --fail-with-body).",
    ),
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """CI regression gate — a minimal, stable verdict contract for pipelines.

    Wraps a regression experiment's already-computed verdict
    (summary.verdict = {passed, eval_delta, failure_delta, max_eval_drop,
    reasons}) with clear gate status semantics so an external CI job can block a
    deploy on a quality/failure regression. Poll while ``status == "pending"``.
    """
    exp = (
        db.query(models.Experiment)
        .filter(models.Experiment.id == experiment_id, models.Experiment.user_id == user_id)
        .first()
    )
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    summary = exp.summary_json if isinstance(exp.summary_json, dict) else {}
    verdict = summary.get("verdict") if isinstance(summary, dict) else None

    if exp.status in ("pending", "running"):
        gate_status, gate_passed = "pending", None
    elif exp.status == "failed":
        gate_status, gate_passed = "error", False
    elif exp.kind != "regression":
        # A gate needs a baseline to compare against; batch runs have no verdict.
        gate_status, gate_passed = "not_applicable", None
    elif not isinstance(verdict, dict):
        gate_status, gate_passed = "error", False
    else:
        gate_passed = bool(verdict.get("passed"))
        gate_status = "passed" if gate_passed else "failed"

    v = verdict if isinstance(verdict, dict) else {}
    body = {
        "experiment_id": str(exp.id),
        "kind": exp.kind,
        "status": gate_status,
        "gate_passed": gate_passed,
        "eval_delta": v.get("eval_delta"),
        "failure_delta": v.get("failure_delta"),
        "max_eval_drop": v.get("max_eval_drop"),
        "reasons": v.get("reasons") or [],
    }

    if strict and gate_status != "passed":
        # 409 so `curl --fail-with-body` (or gh step) fails the CI job outright.
        raise HTTPException(status_code=409, detail=body)
    return body
