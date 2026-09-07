from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.deps import get_current_user_id
from app.schemas.workflow import GuardrailPreviewRequest, GuardrailPreviewResponse
from app.services.cron_utils import cron_is_valid, cron_next_runs
from app.services.guardrail import apply_fail_behavior, validate_guardrail_content
from app.config import settings
from app.services.node_registry import NODE_REGISTRY
from app.services.tracing import is_tracing_enabled

router = APIRouter(prefix="/api/meta", tags=["meta"])


@router.get("/nodes")
def list_node_types(_user_id: UUID = Depends(get_current_user_id)):
    return {"nodes": NODE_REGISTRY}


@router.get("/tracing")
def tracing_config(_user_id: UUID = Depends(get_current_user_id)):
    return {
        "enabled": is_tracing_enabled(),
        "ui_base_url": settings.otel_ui_base_url or None,
    }


@router.get("/ops-config")
def ops_config(_user_id: UUID = Depends(get_current_user_id)):
    """Read-only operational knobs (env-driven) for the Settings page."""
    from app.config import settings as _settings

    return {
        "retention_enabled": _settings.retention_enabled,
        "run_retention_days": _settings.run_retention_days,
        "online_eval_sample_rate": _settings.online_eval_sample_rate,
        "otel_enabled": _settings.otel_enabled,
        "otel_sample_rate": _settings.otel_sample_rate,
        "schedule_poll_seconds": _settings.schedule_poll_seconds,
        "max_concurrent_runs": _settings.max_concurrent_runs,
    }


@router.get("/cron-preview")
def preview_cron(
    expr: str = Query(..., min_length=1),
    count: int = Query(default=3, ge=1, le=10),
    _user_id: UUID = Depends(get_current_user_id),
):
    if not cron_is_valid(expr):
        raise HTTPException(status_code=400, detail="Invalid cron expression")
    runs = cron_next_runs(expr, count=count)
    return {
        "expr": expr.strip(),
        "next_runs": [dt.isoformat() for dt in runs],
    }


@router.post("/guardrail-preview", response_model=GuardrailPreviewResponse)
def preview_guardrail(
    payload: GuardrailPreviewRequest,
    _user_id: UUID = Depends(get_current_user_id),
):
    result = validate_guardrail_content(payload.text, payload.rules)
    fail_behavior = payload.rules.get("fail_behavior", "block")
    would_block = not result.passed and fail_behavior == "block"
    if fail_behavior == "route":
        would_block = False
    if not result.passed and fail_behavior in {"warn", "mask", "fallback"}:
        result = apply_fail_behavior(
            result,
            fail_behavior,
            "preview",
            content=payload.text,
            rules=payload.rules,
        )
    return GuardrailPreviewResponse(
        passed=result.passed,
        message=result.message,
        severity=result.severity,
        would_block=would_block,
    )