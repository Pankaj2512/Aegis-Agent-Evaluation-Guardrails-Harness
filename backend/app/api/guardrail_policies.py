"""Reusable guardrail policy bundles — define once, attach to any workflow."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user_id
from app.db import models
from app.db.database import get_db
from app.services.guardrail_policy_templates import list_policy_templates

router = APIRouter(prefix="/api/guardrail-policies", tags=["guardrail-policies"])


class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    rules_json: dict = Field(default_factory=dict)


class PolicyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    rules_json: dict | None = None


def _serialize(policy: models.GuardrailPolicy) -> dict:
    return {
        "id": str(policy.id),
        "name": policy.name,
        "description": policy.description,
        "rules_json": policy.rules_json,
        "created_at": policy.created_at.isoformat() if policy.created_at else None,
        "updated_at": policy.updated_at.isoformat() if policy.updated_at else None,
    }


def _get_policy(db: Session, policy_id: UUID, user_id: UUID) -> models.GuardrailPolicy:
    policy = (
        db.query(models.GuardrailPolicy)
        .filter(models.GuardrailPolicy.id == policy_id, models.GuardrailPolicy.user_id == user_id)
        .first()
    )
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy


@router.get("/templates")
def list_templates(_user_id: UUID = Depends(get_current_user_id)):
    """Built-in guardrail policy templates — one-click starting points to adopt."""
    return list_policy_templates()


@router.get("")
def list_policies(db: Session = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    rows = (
        db.query(models.GuardrailPolicy)
        .filter(models.GuardrailPolicy.user_id == user_id)
        .order_by(models.GuardrailPolicy.created_at.desc())
        .all()
    )
    return [_serialize(p) for p in rows]


@router.post("", status_code=201)
def create_policy(
    payload: PolicyCreate,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    policy = models.GuardrailPolicy(
        user_id=user_id,
        name=payload.name,
        description=payload.description,
        rules_json=payload.rules_json,
    )
    db.add(policy)
    db.commit()
    return _serialize(policy)


@router.patch("/{policy_id}")
def update_policy(
    policy_id: UUID,
    payload: PolicyUpdate,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    policy = _get_policy(db, policy_id, user_id)
    if payload.name is not None:
        policy.name = payload.name
    if payload.description is not None:
        policy.description = payload.description
    if payload.rules_json is not None:
        policy.rules_json = payload.rules_json
    db.commit()
    return _serialize(policy)


@router.delete("/{policy_id}", status_code=204)
def delete_policy(
    policy_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    policy = _get_policy(db, policy_id, user_id)
    db.delete(policy)
    db.commit()
    return None


def enrich_graph_guardrail_policies(graph_json: dict, db: Session, user_id: UUID) -> dict:
    """Resolve guardrail nodes' policyId into concrete rules before compile.

    Node-level rules override bundle rules so a workflow can specialize a
    shared policy without editing it.
    """
    nodes = graph_json.get("nodes") or []
    policy_ids: list[UUID] = []
    for node in nodes:
        data = node.get("data") or {}
        if data.get("nodeType") != "guardrail":
            continue
        policy_id = (data.get("rules") or {}).get("policy_id") or data.get("policyId")
        if policy_id:
            try:
                policy_ids.append(UUID(str(policy_id)))
            except ValueError:
                continue
    if not policy_ids:
        return graph_json

    policies = {
        str(p.id): p.rules_json or {}
        for p in db.query(models.GuardrailPolicy)
        .filter(models.GuardrailPolicy.user_id == user_id, models.GuardrailPolicy.id.in_(policy_ids))
        .all()
    }
    for node in nodes:
        data = node.get("data") or {}
        if data.get("nodeType") != "guardrail":
            continue
        rules = dict(data.get("rules") or {})
        policy_id = str(rules.get("policy_id") or data.get("policyId") or "")
        bundle = policies.get(policy_id)
        if bundle:
            data["rules"] = {**bundle, **rules}
            node["data"] = data
    return graph_json
