"""Built-in and user-defined evaluation preset helpers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import models
from app.services.eval import EVAL_PRESETS, SCORE_WEIGHTS, build_eval_instruction


def builtin_preset_rows() -> list[dict[str, Any]]:
    return [
        {
            "id": key,
            "label": value["label"],
            "criteria": value["criteria"],
            "instruction": value.get("instruction") or build_eval_instruction(key, value["criteria"]),
            "score_weights": dict(SCORE_WEIGHTS),
            "source": "builtin",
            "eval_type": "llm",
        }
        for key, value in EVAL_PRESETS.items()
    ]


def list_user_presets(db: Session, user_id: UUID) -> list[models.EvaluationPreset]:
    return (
        db.query(models.EvaluationPreset)
        .filter(models.EvaluationPreset.user_id == user_id)
        .order_by(models.EvaluationPreset.name.asc())
        .all()
    )


def user_preset_row(row: models.EvaluationPreset) -> dict[str, Any]:
    weights = row.score_weights or dict(SCORE_WEIGHTS)
    return {
        "id": str(row.id),
        "label": row.label,
        "criteria": row.criteria,
        "instruction": row.instruction or build_eval_instruction(None, row.criteria),
        "score_weights": weights,
        "source": "custom",
        "eval_type": row.eval_type or "llm",
    }


def list_all_presets(db: Session, user_id: UUID) -> list[dict[str, Any]]:
    return [*builtin_preset_rows(), *[user_preset_row(row) for row in list_user_presets(db, user_id)]]


def get_preset_config(
    db: Session,
    user_id: UUID,
    preset_id: str | None,
) -> dict[str, Any] | None:
    if not preset_id:
        return None
    if preset_id in EVAL_PRESETS:
        builtin = EVAL_PRESETS[preset_id]
        return {
            "criteria": builtin["criteria"],
            "instruction": build_eval_instruction(preset_id, builtin["criteria"]),
            "score_weights": dict(SCORE_WEIGHTS),
            "eval_type": "llm",
        }
    try:
        preset_uuid = UUID(str(preset_id))
    except ValueError:
        return None
    row = (
        db.query(models.EvaluationPreset)
        .filter(models.EvaluationPreset.id == preset_uuid, models.EvaluationPreset.user_id == user_id)
        .first()
    )
    if not row:
        return None
    return {
        "criteria": row.criteria,
        "instruction": row.instruction or build_eval_instruction(None, row.criteria),
        "score_weights": row.score_weights or dict(SCORE_WEIGHTS),
        "eval_type": row.eval_type or "llm",
    }


def _batch_load_custom_presets(
    db: Session,
    user_id: UUID,
    preset_ids: list[UUID],
) -> dict[str, dict[str, Any]]:
    if not preset_ids:
        return {}
    rows = (
        db.query(models.EvaluationPreset)
        .filter(
            models.EvaluationPreset.user_id == user_id,
            models.EvaluationPreset.id.in_(preset_ids),
        )
        .all()
    )
    return {
        str(row.id): {
            "criteria": row.criteria,
            "instruction": row.instruction or build_eval_instruction(None, row.criteria),
            "score_weights": row.score_weights or dict(SCORE_WEIGHTS),
            "eval_type": row.eval_type or "llm",
        }
        for row in rows
    }


def enrich_graph_eval_presets(graph_json: dict, db: Session, user_id: UUID) -> dict:
    """Inject custom preset criteria/weights into graph nodes before compile."""
    nodes = graph_json.get("nodes") or []
    custom_ids: list[UUID] = []
    for node in nodes:
        data = node.get("data") or {}
        if data.get("nodeType") != "evaluation":
            continue
        preset_id = data.get("evalCustomPresetId") or data.get("evalPreset")
        if not preset_id or str(preset_id) in EVAL_PRESETS:
            continue
        try:
            custom_ids.append(UUID(str(preset_id)))
        except ValueError:
            continue
    preset_map = _batch_load_custom_presets(db, user_id, custom_ids)

    changed = False
    for node in nodes:
        data = node.get("data") or {}
        if data.get("nodeType") != "evaluation":
            continue
        preset_id = data.get("evalCustomPresetId") or data.get("evalPreset")
        if not preset_id:
            continue
        preset_key = str(preset_id)
        if preset_key in EVAL_PRESETS:
            builtin = EVAL_PRESETS[preset_key]
            config = {
                "criteria": builtin["criteria"],
                "instruction": build_eval_instruction(preset_key, builtin["criteria"]),
                "score_weights": dict(SCORE_WEIGHTS),
                "eval_type": "llm",
            }
        else:
            config = preset_map.get(preset_key) or get_preset_config(db, user_id, preset_key)
        if not config:
            continue
        if config.get("criteria"):
            data["criteria"] = config["criteria"]
        if config.get("instruction"):
            data["evalInstruction"] = config["instruction"]
        if config.get("score_weights"):
            data["scoreWeights"] = config["score_weights"]
        node["data"] = data
        changed = True
    if changed:
        return {**graph_json, "nodes": nodes}
    return graph_json