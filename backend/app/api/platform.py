"""Platform surface: publish/rollback, stable invoke API, external trace ingestion, audit."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from fastapi import status

from app.auth.deps import get_current_user_id
from app.config import settings
from app.db import models
from app.db.database import SessionLocal, get_db
from app.services.audit import record_audit
from app.services.budgets import check_workflow_budget
from app.services.deploy_descriptor import build_deploy_descriptor
from app.services.executor import active_run_count, schedule_run
from app.services.async_tasks import schedule_task
from app.services.graph_validation import GraphValidationError, validate_workflow_graph
from app.services.run_concurrency import count_active_runs
from app.services.workflow_capabilities import workflow_needs_gemini

router = APIRouter(tags=["platform"])


# ---------- publish / rollback (environments-lite) ----------


class PublishPayload(BaseModel):
    version_id: UUID


@router.post("/api/workflows/{workflow_id}/publish")
def publish_version(
    workflow_id: UUID,
    payload: PublishPayload,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    workflow = (
        db.query(models.Workflow)
        .filter(models.Workflow.id == workflow_id, models.Workflow.user_id == user_id)
        .first()
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    version = (
        db.query(models.WorkflowVersion)
        .filter(
            models.WorkflowVersion.id == payload.version_id,
            models.WorkflowVersion.workflow_id == workflow_id,
        )
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    previous = workflow.published_version_id
    workflow.published_version_id = version.id
    record_audit(
        db,
        user_id,
        "publish",
        "workflow",
        workflow_id,
        {"version": version.version_number, "previous_version_id": str(previous) if previous else None},
    )
    db.commit()
    return {
        "workflow_id": str(workflow_id),
        "published_version_id": str(version.id),
        "published_version_number": version.version_number,
    }


@router.get("/api/workflows/{workflow_id}/published")
def get_published(
    workflow_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    workflow = (
        db.query(models.Workflow)
        .filter(models.Workflow.id == workflow_id, models.Workflow.user_id == user_id)
        .first()
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    version_number = None
    if workflow.published_version_id:
        version = (
            db.query(models.WorkflowVersion)
            .filter(models.WorkflowVersion.id == workflow.published_version_id)
            .first()
        )
        version_number = version.version_number if version else None
    return {
        "published_version_id": str(workflow.published_version_id)
        if workflow.published_version_id
        else None,
        "published_version_number": version_number,
    }


@router.get("/api/workflows/{workflow_id}/deploy")
def get_deploy_descriptor(
    workflow_id: UUID,
    request: Request,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Deploy descriptor for the currently-published version.

    Returns the stable invoke URL, a ready-to-paste cURL snippet, and an MCP
    tool descriptor whose input schema is derived from the workflow's
    input_schema node. 409 when no version has been published yet.
    """
    workflow = (
        db.query(models.Workflow)
        .filter(models.Workflow.id == workflow_id, models.Workflow.user_id == user_id)
        .first()
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if not workflow.published_version_id:
        raise HTTPException(
            status_code=409,
            detail="Workflow has no published version. Publish a version before deploying.",
        )
    version = (
        db.query(models.WorkflowVersion)
        .filter(models.WorkflowVersion.id == workflow.published_version_id)
        .first()
    )
    if not version:
        raise HTTPException(
            status_code=409,
            detail="Published version no longer exists. Re-publish a version before deploying.",
        )

    base_url = str(request.base_url).rstrip("/")
    return build_deploy_descriptor(
        workflow_id=str(workflow_id),
        workflow_name=workflow.name,
        description=workflow.description,
        published_version_id=str(version.id),
        published_version_number=version.version_number,
        graph_json=version.graph_json or {},
        base_url=base_url,
    )


# ---------- stable invoke API (workflow-as-API) ----------


class InvokePayload(BaseModel):
    input: str = Field(min_length=1, max_length=20_000)
    # Thread multi-turn calls into one session (e.g. a chatbot conversation)
    # and tag them for filtering — surfaced in the observability Sessions view.
    session_id: str | None = Field(default=None, max_length=128)
    tags: list[str] | None = None


@router.post("/v1/workflows/{workflow_id}/invoke")
async def invoke_workflow(
    workflow_id: UUID,
    payload: InvokePayload,
    wait: bool = Query(default=False, description="Block until the run finishes (max 90s)"),
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Run the workflow's *published* version (falls back to latest)."""
    workflow = (
        db.query(models.Workflow)
        .filter(models.Workflow.id == workflow_id, models.Workflow.user_id == user_id)
        .first()
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")

    breach = check_workflow_budget(db, workflow)
    if breach:
        raise HTTPException(status_code=429, detail=breach)

    version = None
    if workflow.published_version_id:
        version = (
            db.query(models.WorkflowVersion)
            .filter(models.WorkflowVersion.id == workflow.published_version_id)
            .first()
        )
    if version is None:
        version = (
            db.query(models.WorkflowVersion)
            .filter(models.WorkflowVersion.workflow_id == workflow_id)
            .order_by(models.WorkflowVersion.version_number.desc())
            .first()
        )
    if version is None:
        raise HTTPException(status_code=404, detail="Workflow has no versions")

    try:
        validate_workflow_graph(version.graph_json or {})
    except GraphValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    in_memory_runs = active_run_count()
    if settings.run_execution_mode == "worker":
        active = max(in_memory_runs, count_active_runs(db))
    else:
        active = in_memory_runs
    if active >= settings.max_concurrent_runs:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many concurrent runs (limit: {settings.max_concurrent_runs})",
        )

    if workflow_needs_gemini(version.graph_json or {}) and not settings.google_api_key:
        raise HTTPException(
            status_code=400,
            detail="GOOGLE_API_KEY is not configured. Add it to .env to run LLM workflows.",
        )

    run = models.WorkflowRun(
        workflow_version_id=version.id,
        status="pending",
        input_text=payload.input,
        session_id=(payload.session_id or "").strip() or None,
        tags_json=(
            [t.strip() for t in payload.tags if isinstance(t, str) and t.strip()]
            if payload.tags
            else None
        ),
    )
    db.add(run)
    db.commit()
    run_id = run.id
    if settings.run_execution_mode != "worker":
        schedule_run(run_id)

    if not wait:
        return {"run_id": str(run_id), "status": "pending", "version": version.version_number}

    deadline = 90.0
    poll = 0.5
    while deadline > 0:
        await asyncio.sleep(poll)
        deadline -= poll
        session = SessionLocal(expire_on_commit=False)
        try:
            current = (
                session.query(models.WorkflowRun).filter(models.WorkflowRun.id == run_id).first()
            )
            if current and current.status in {"completed", "failed", "cancelled"}:
                metrics = current.metrics_json or {}
                return {
                    "run_id": str(run_id),
                    "status": current.status,
                    "output": current.final_output,
                    "version": version.version_number,
                    "eval_aggregate": metrics.get("eval_aggregate"),
                    "total_cost_usd": metrics.get("total_cost_usd"),
                    "latency_ms": metrics.get("latency_ms"),
                }
        finally:
            session.close()
    return {"run_id": str(run_id), "status": "running", "version": version.version_number}


# ---------- external trace ingestion ----------


class IngestNodeEvent(BaseModel):
    node_id: str
    label: str | None = None
    node_type: str = "external"
    status: str = "completed"
    output: str | None = None
    latency_ms: int | None = None


class IngestRunPayload(BaseModel):
    workflow_name: str = Field(min_length=1, max_length=255)
    input: str = Field(default="", max_length=50_000)
    output: str | None = Field(default=None, max_length=100_000)
    status: str = "completed"
    latency_ms: int | None = None
    total_tokens: int | None = None
    total_cost_usd: float | None = None
    node_events: list[IngestNodeEvent] = Field(default_factory=list, max_length=100)
    evaluate: bool = Field(default=False, description="Score the output with the LLM judge async")
    session_id: str | None = Field(default=None, max_length=128)
    tags: list[str] | None = None


EXTERNAL_DESCRIPTION = "External agent (ingested traces)"


@router.post("/v1/ingest/runs", status_code=201)
async def ingest_run(
    payload: IngestRunPayload,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Record a run executed OUTSIDE Aegis so it gets dashboards, clusters, and evals.

    The named workflow is created on first ingest (marked external). This is the
    v1 ingestion path for LangChain/raw-SDK agents; OTLP arrives later.
    """
    workflow = (
        db.query(models.Workflow)
        .filter(models.Workflow.user_id == user_id, models.Workflow.name == payload.workflow_name)
        .first()
    )
    if workflow is None:
        workflow = models.Workflow(
            user_id=user_id, name=payload.workflow_name, description=EXTERNAL_DESCRIPTION
        )
        db.add(workflow)
        db.flush()
    version = (
        db.query(models.WorkflowVersion)
        .filter(models.WorkflowVersion.workflow_id == workflow.id)
        .order_by(models.WorkflowVersion.version_number.desc())
        .first()
    )
    if version is None:
        version = models.WorkflowVersion(
            workflow_id=workflow.id, version_number=1, graph_json={"nodes": [], "edges": [], "external": True}
        )
        db.add(version)
        db.flush()

    if payload.status not in {"completed", "failed", "cancelled"}:
        raise HTTPException(status_code=400, detail="status must be completed|failed|cancelled")

    now = datetime.now(timezone.utc)
    metrics: dict = {"ingested": True}
    if payload.latency_ms is not None:
        metrics["latency_ms"] = payload.latency_ms
    if payload.total_tokens is not None:
        metrics["total_tokens"] = payload.total_tokens
    if payload.total_cost_usd is not None:
        metrics["total_cost_usd"] = payload.total_cost_usd

    run = models.WorkflowRun(
        workflow_version_id=version.id,
        status=payload.status,
        input_text=payload.input,
        final_output=payload.output,
        metrics_json=metrics,
        started_at=now,
        completed_at=now,
        session_id=(payload.session_id or "").strip() or None,
        tags_json=(
            [t.strip() for t in payload.tags if isinstance(t, str) and t.strip()]
            if payload.tags
            else None
        ),
    )
    db.add(run)
    db.flush()
    for event in payload.node_events:
        db.add(
            models.NodeResult(
                run_id=run.id,
                node_id=event.node_id,
                node_type=event.node_type,
                node_label=event.label or event.node_id,
                status=event.status,
                output=event.output,
                latency_ms=event.latency_ms,
            )
        )
    record_audit(db, user_id, "ingest", "run", run.id, {"workflow": payload.workflow_name})
    db.commit()

    if payload.evaluate and payload.output:
        from app.services.executor import _sampled_online_eval

        schedule_task(_sampled_online_eval(run.id, payload.output, payload.input))

    return {"run_id": str(run.id), "workflow_id": str(workflow.id)}


# ---------- audit log ----------


@router.get("/api/audit")
def list_audit(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    rows = (
        db.query(models.AuditLog)
        .filter(models.AuditLog.user_id == user_id)
        .order_by(models.AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": str(row.id),
            "action": row.action,
            "entity_type": row.entity_type,
            "entity_id": row.entity_id,
            "meta": row.meta,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
