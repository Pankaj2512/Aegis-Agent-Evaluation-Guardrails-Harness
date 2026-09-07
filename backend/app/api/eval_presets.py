from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user_id
from app.db import models
from app.db.database import get_db
from app.schemas.eval_preset import (
    EvalPresetCreate,
    EvalPresetListItem,
    EvalPresetResponse,
    EvalPresetUpdate,
    EvalPreviewRequest,
    RagPreviewRequest,
)
from app.services.eval import SCORE_WEIGHTS
from app.services.eval_preset_service import list_all_presets
from app.services.eval_preview import preview_eval
from app.services.rag_metrics import score_rag

router = APIRouter(prefix="/api/eval-presets", tags=["eval-presets"])


def _as_list_item(row: models.EvaluationPreset) -> EvalPresetListItem:
    return EvalPresetListItem(
        id=row.id,
        name=row.name,
        label=row.label,
        criteria=row.criteria,
        instruction=row.instruction,
        score_weights=row.score_weights,
        eval_type=row.eval_type,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=list[EvalPresetResponse])
def list_eval_presets(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    return list_all_presets(db, user_id)


@router.post("", response_model=EvalPresetListItem)
def create_eval_preset(
    payload: EvalPresetCreate,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    existing = (
        db.query(models.EvaluationPreset)
        .filter(
            models.EvaluationPreset.user_id == user_id,
            models.EvaluationPreset.name == payload.name,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Preset '{payload.name}' already exists")

    row = models.EvaluationPreset(
        user_id=user_id,
        name=payload.name.strip(),
        label=payload.label.strip(),
        criteria=payload.criteria.strip(),
        instruction=(payload.instruction or "").strip() or None,
        score_weights=payload.score_weights or dict(SCORE_WEIGHTS),
        eval_type=(payload.eval_type or "llm").lower(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _as_list_item(row)


@router.patch("/{preset_id}", response_model=EvalPresetListItem)
def update_eval_preset(
    preset_id: UUID,
    payload: EvalPresetUpdate,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    row = (
        db.query(models.EvaluationPreset)
        .filter(models.EvaluationPreset.id == preset_id, models.EvaluationPreset.user_id == user_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Preset not found")
    fields = payload.model_dump(exclude_unset=True)
    if "label" in fields and fields["label"]:
        row.label = fields["label"].strip()
    if "criteria" in fields and fields["criteria"] is not None:
        row.criteria = fields["criteria"].strip()
    if "instruction" in fields:
        row.instruction = (fields["instruction"] or "").strip() or None
    if "score_weights" in fields and fields["score_weights"] is not None:
        row.score_weights = fields["score_weights"]
    db.commit()
    db.refresh(row)
    return _as_list_item(row)


@router.post("/preview")
def preview_eval_preset(
    payload: EvalPreviewRequest,
    user_id: UUID = Depends(get_current_user_id),
):
    """Run the LLM judge once on a sample so authors can iterate on a rubric."""
    return preview_eval(
        payload.input_text,
        payload.output_text,
        criteria=payload.criteria,
        instruction=payload.instruction,
        score_weights=payload.score_weights,
    )


@router.post("/rag-preview")
def rag_preview(
    payload: RagPreviewRequest,
    user_id: UUID = Depends(get_current_user_id),
):
    """RAG-specific scoring: context precision / faithfulness / answer relevance
    for a (question, retrieved-context, answer) triple."""
    return score_rag(payload.question, payload.answer, payload.context)


@router.delete("/{preset_id}")
def delete_eval_preset(
    preset_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    row = (
        db.query(models.EvaluationPreset)
        .filter(models.EvaluationPreset.id == preset_id, models.EvaluationPreset.user_id == user_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="Preset not found")
    db.delete(row)
    db.commit()
    return {"status": "deleted", "id": str(preset_id)}