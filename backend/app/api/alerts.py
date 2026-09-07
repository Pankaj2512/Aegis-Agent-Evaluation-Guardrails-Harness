"""Alert rules and fired events."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user_id
from app.db import models
from app.db.database import get_db
from app.services.alerts import SUPPORTED_METRICS

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertRuleCreate(BaseModel):
    workflow_id: UUID | None = None
    metric: str
    operator: str = "gt"
    threshold: float
    window_minutes: int = Field(default=60, ge=5, le=1440)
    comparison: str = "absolute"
    baseline_window_minutes: int | None = Field(default=None, ge=10, le=10080)
    channel_url: str | None = None
    enabled: bool = True


class AlertRuleUpdate(BaseModel):
    workflow_id: UUID | None = None
    metric: str | None = None
    operator: str | None = None
    threshold: float | None = None
    window_minutes: int | None = Field(default=None, ge=5, le=1440)
    comparison: str | None = None
    baseline_window_minutes: int | None = Field(default=None, ge=10, le=10080)
    channel_url: str | None = None
    enabled: bool | None = None


_COMPARISONS = ("absolute", "baseline")


def _serialize(rule: models.AlertRule) -> dict:
    return {
        "id": str(rule.id),
        "workflow_id": str(rule.workflow_id) if rule.workflow_id else None,
        "metric": rule.metric,
        "operator": rule.operator,
        "threshold": rule.threshold,
        "window_minutes": rule.window_minutes,
        "comparison": getattr(rule, "comparison", "absolute") or "absolute",
        "baseline_window_minutes": rule.baseline_window_minutes,
        "channel_url": rule.channel_url,
        "enabled": rule.enabled,
        "last_fired_at": rule.last_fired_at.isoformat() if rule.last_fired_at else None,
    }


@router.get("")
def list_rules(db: Session = Depends(get_db), user_id: UUID = Depends(get_current_user_id)):
    rules = (
        db.query(models.AlertRule)
        .filter(models.AlertRule.user_id == user_id)
        .order_by(models.AlertRule.created_at.desc())
        .all()
    )
    return [_serialize(r) for r in rules]


@router.post("", status_code=201)
def create_rule(
    payload: AlertRuleCreate,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    if payload.metric not in SUPPORTED_METRICS:
        raise HTTPException(status_code=400, detail=f"metric must be one of {sorted(SUPPORTED_METRICS)}")
    if payload.operator not in ("gt", "lt"):
        raise HTTPException(status_code=400, detail="operator must be gt or lt")
    if payload.comparison not in _COMPARISONS:
        raise HTTPException(status_code=400, detail=f"comparison must be one of {list(_COMPARISONS)}")
    rule = models.AlertRule(
        user_id=user_id,
        workflow_id=payload.workflow_id,
        metric=payload.metric,
        operator=payload.operator,
        threshold=payload.threshold,
        window_minutes=payload.window_minutes,
        comparison=payload.comparison,
        baseline_window_minutes=payload.baseline_window_minutes,
        channel_url=payload.channel_url,
        enabled=payload.enabled,
    )
    db.add(rule)
    db.commit()
    return _serialize(rule)


@router.patch("/{rule_id}")
def update_rule(
    rule_id: UUID,
    payload: AlertRuleUpdate,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    rule = (
        db.query(models.AlertRule)
        .filter(models.AlertRule.id == rule_id, models.AlertRule.user_id == user_id)
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    fields = payload.model_dump(exclude_unset=True)
    if "metric" in fields and fields["metric"] not in SUPPORTED_METRICS:
        raise HTTPException(status_code=400, detail=f"metric must be one of {sorted(SUPPORTED_METRICS)}")
    if "operator" in fields and fields["operator"] not in ("gt", "lt"):
        raise HTTPException(status_code=400, detail="operator must be gt or lt")
    if "comparison" in fields and fields["comparison"] not in _COMPARISONS:
        raise HTTPException(status_code=400, detail=f"comparison must be one of {list(_COMPARISONS)}")
    for key, value in fields.items():
        setattr(rule, key, value)
    db.commit()
    return _serialize(rule)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    rule = (
        db.query(models.AlertRule)
        .filter(models.AlertRule.id == rule_id, models.AlertRule.user_id == user_id)
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    db.query(models.AlertEvent).filter(models.AlertEvent.rule_id == rule.id).delete()
    db.delete(rule)
    db.commit()
    return None


@router.get("/events")
def list_events(
    limit: int = 50,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    # Clamp so negative/zero limits never reach SQL (Postgres rejects LIMIT -1).
    safe_limit = max(1, min(int(limit or 50), 200))
    rows = (
        db.query(models.AlertEvent, models.AlertRule)
        .join(models.AlertRule, models.AlertRule.id == models.AlertEvent.rule_id)
        .filter(models.AlertRule.user_id == user_id)
        .order_by(models.AlertEvent.fired_at.desc())
        .limit(safe_limit)
        .all()
    )
    return [
        {
            "id": str(event.id),
            "rule_id": str(event.rule_id),
            "metric": rule.metric,
            "value": event.value,
            "message": event.message,
            "fired_at": event.fired_at.isoformat() if event.fired_at else None,
        }
        for event, rule in rows
    ]
