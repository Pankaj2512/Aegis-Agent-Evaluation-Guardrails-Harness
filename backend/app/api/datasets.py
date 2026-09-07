"""Golden datasets: CRUD, JSON import, and add-from-run."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user_id
from app.db import models
from app.db.database import get_db

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


class DatasetCreate(BaseModel):
    workflow_id: UUID
    name: str = Field(min_length=1, max_length=255)


class DatasetItemCreate(BaseModel):
    input_text: str = Field(min_length=1)
    expected_output: str | None = None
    tags: dict | None = None


class DatasetImport(BaseModel):
    items: list[DatasetItemCreate] = Field(min_length=1, max_length=500)


class DatasetCapture(BaseModel):
    # recent: latest runs · failed: only failures · low_eval: eval below max_eval
    filter: str = "recent"
    limit: int = Field(default=20, ge=1, le=200)
    max_eval: float = Field(default=3.0, ge=0, le=5)


def _get_user_dataset(db: Session, dataset_id: UUID, user_id: UUID) -> models.Dataset:
    dataset = (
        db.query(models.Dataset)
        .filter(models.Dataset.id == dataset_id, models.Dataset.user_id == user_id)
        .first()
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


def _serialize(dataset: models.Dataset, item_count: int | None = None) -> dict:
    return {
        "id": str(dataset.id),
        "workflow_id": str(dataset.workflow_id),
        "name": dataset.name,
        "item_count": item_count if item_count is not None else len(dataset.items),
        "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
    }


@router.get("")
def list_datasets(
    workflow_id: UUID | None = None,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    query = db.query(models.Dataset).filter(models.Dataset.user_id == user_id)
    if workflow_id:
        query = query.filter(models.Dataset.workflow_id == workflow_id)
    return [_serialize(d) for d in query.order_by(models.Dataset.created_at.desc()).all()]


@router.post("", status_code=201)
def create_dataset(
    payload: DatasetCreate,
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
    dataset = models.Dataset(user_id=user_id, workflow_id=payload.workflow_id, name=payload.name)
    db.add(dataset)
    db.commit()
    return _serialize(dataset, item_count=0)


@router.get("/{dataset_id}")
def get_dataset(
    dataset_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    dataset = _get_user_dataset(db, dataset_id, user_id)
    return {
        **_serialize(dataset),
        "items": [
            {
                "id": str(item.id),
                "input_text": item.input_text,
                "expected_output": item.expected_output,
                "tags": item.tags,
            }
            for item in dataset.items
        ],
    }


@router.delete("/{dataset_id}", status_code=204)
def delete_dataset(
    dataset_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    dataset = _get_user_dataset(db, dataset_id, user_id)
    db.delete(dataset)
    db.commit()
    return None


@router.post("/{dataset_id}/items", status_code=201)
def add_item(
    dataset_id: UUID,
    payload: DatasetItemCreate,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    dataset = _get_user_dataset(db, dataset_id, user_id)
    item = models.DatasetItem(
        dataset_id=dataset.id,
        input_text=payload.input_text,
        expected_output=payload.expected_output,
        tags=payload.tags,
    )
    db.add(item)
    db.commit()
    return {"id": str(item.id)}


@router.post("/{dataset_id}/import")
def import_items(
    dataset_id: UUID,
    payload: DatasetImport,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    dataset = _get_user_dataset(db, dataset_id, user_id)
    for entry in payload.items:
        db.add(
            models.DatasetItem(
                dataset_id=dataset.id,
                input_text=entry.input_text,
                expected_output=entry.expected_output,
                tags=entry.tags,
            )
        )
    db.commit()
    return {"imported": len(payload.items)}


@router.delete("/{dataset_id}/items/{item_id}", status_code=204)
def delete_item(
    dataset_id: UUID,
    item_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    _get_user_dataset(db, dataset_id, user_id)
    item = (
        db.query(models.DatasetItem)
        .filter(models.DatasetItem.id == item_id, models.DatasetItem.dataset_id == dataset_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    db.delete(item)
    db.commit()
    return None


@router.post("/{dataset_id}/add-run/{run_id}", status_code=201)
def add_run_input(
    dataset_id: UUID,
    run_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Grow the golden set from real traffic: copy a run's input (+ output as expected)."""
    dataset = _get_user_dataset(db, dataset_id, user_id)
    # Ownership join (mirrors runs._get_user_run): never leak another tenant's
    # run input/output into this user's dataset.
    run = (
        db.query(models.WorkflowRun)
        .join(models.WorkflowVersion)
        .join(models.Workflow)
        .filter(models.WorkflowRun.id == run_id, models.Workflow.user_id == user_id)
        .first()
    )
    if not run or not (run.input_text or "").strip():
        raise HTTPException(status_code=404, detail="Run not found or has no input")
    item = models.DatasetItem(
        dataset_id=dataset.id,
        input_text=run.input_text,
        expected_output=run.final_output,
        tags={"source_run": str(run_id)},
    )
    db.add(item)
    db.commit()
    return {"id": str(item.id)}


@router.post("/{dataset_id}/capture")
def capture_runs(
    dataset_id: UUID,
    payload: DatasetCapture,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Bulk-grow a golden set from production traffic.

    Captures this workflow's recent / failed / low-eval runs into the dataset
    (input + output as expected), skipping runs already captured (deduped by the
    ``source_run`` tag). Turns real traffic — especially the failures and weak
    evals worth regression-testing — into a labelled set in one click.
    """
    dataset = _get_user_dataset(db, dataset_id, user_id)

    query = (
        db.query(models.WorkflowRun)
        .join(models.WorkflowVersion, models.WorkflowRun.workflow_version_id == models.WorkflowVersion.id)
        .filter(models.WorkflowVersion.workflow_id == dataset.workflow_id)
        .order_by(models.WorkflowRun.created_at.desc())
    )
    if payload.filter == "failed":
        query = query.filter(models.WorkflowRun.status == "failed")
    # Over-fetch so the low_eval / dedup passes still have `limit` candidates.
    candidates = query.limit(min(payload.limit * 5, 500)).all()

    if payload.filter == "low_eval":
        def _low(run: models.WorkflowRun) -> bool:
            agg = (run.metrics_json or {}).get("eval_aggregate")
            return isinstance(agg, (int, float)) and agg < payload.max_eval

        candidates = [r for r in candidates if _low(r)]

    existing = {
        (item.tags or {}).get("source_run")
        for item in db.query(models.DatasetItem)
        .filter(models.DatasetItem.dataset_id == dataset.id)
        .all()
    }

    added = 0
    skipped = 0
    for run in candidates:
        if added >= payload.limit:
            break
        if not (run.input_text or "").strip():
            continue
        if str(run.id) in existing:
            skipped += 1
            continue
        db.add(
            models.DatasetItem(
                dataset_id=dataset.id,
                input_text=run.input_text,
                expected_output=run.final_output,
                tags={"source_run": str(run.id), "capture": payload.filter},
            )
        )
        existing.add(str(run.id))
        added += 1
    db.commit()
    return {"added": added, "skipped": skipped, "filter": payload.filter}
