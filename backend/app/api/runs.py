import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import get_current_user_id
from app.config import settings
from app.db import models
from app.db.database import SessionLocal, get_db
from app.schemas.run import (
    RunApprovalPayload,
    RunCreate,
    RunListItem,
    RunResponse,
    RunTimelineResponse,
    TimelineNode,
)
from app.services.approval_service import submit_approval
from app.services.executor import (
    active_run_count,
    cancel_run,
    register_authoring_overrides,
    schedule_run,
    stream_run_events,
)
from app.services.run_concurrency import count_active_runs
from app.services.run_filters import apply_run_quality_sql_filters
from app.services.graph_validation import GraphValidationError, validate_workflow_graph
from app.services.workflow_capabilities import workflow_needs_gemini

router = APIRouter(prefix="/api/runs", tags=["runs"])


def _get_user_run(db: Session, run_id: UUID, user_id: UUID) -> models.WorkflowRun:
    run = (
        db.query(models.WorkflowRun)
        .options(
            joinedload(models.WorkflowRun.version).joinedload(models.WorkflowVersion.workflow),
            joinedload(models.WorkflowRun.node_results),
        )
        .join(models.WorkflowVersion)
        .join(models.Workflow)
        .filter(models.WorkflowRun.id == run_id, models.Workflow.user_id == user_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("", response_model=list[RunListItem])
def list_runs(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    status_filter: str | None = Query(default=None, alias="status"),
    eval_passed: bool | None = Query(default=None),
    guardrail_blocked: bool | None = Query(default=None),
    has_eval: bool | None = Query(default=None),
    session_id: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    query = (
        db.query(models.WorkflowRun)
        .options(joinedload(models.WorkflowRun.version).joinedload(models.WorkflowVersion.workflow))
        .join(models.WorkflowVersion)
        .join(models.Workflow)
        .filter(models.Workflow.user_id == user_id)
    )
    if status_filter:
        query = query.filter(models.WorkflowRun.status == status_filter)
    if session_id:
        query = query.filter(models.WorkflowRun.session_id == session_id)
    query = apply_run_quality_sql_filters(
        query,
        has_eval=has_eval,
        eval_passed=eval_passed,
        guardrail_blocked=guardrail_blocked,
    )
    if tag:
        # Push tag filter into SQL before LIMIT/OFFSET so paging is correct.
        dialect_name = (db.get_bind().dialect.name if db.get_bind() else "sqlite")
        if dialect_name == "postgresql":
            query = query.filter(models.WorkflowRun.tags_json.contains([tag]))
        else:
            # SQLite JSON: match the tag as a JSON string element.
            from sqlalchemy import String, cast

            query = query.filter(
                cast(models.WorkflowRun.tags_json, String).like(f'%"{tag}"%')
            )
    runs = (
        query.order_by(models.WorkflowRun.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    items: list[RunListItem] = []
    for run in runs:
        workflow = run.version.workflow if run.version else None
        metrics = run.metrics_json or {}
        run_eval_passed = metrics.get("eval_passed")
        run_guardrail_blocked = bool(metrics.get("guardrail_blocked"))
        run_eval_aggregate = metrics.get("eval_aggregate")
        items.append(
            RunListItem(
                id=run.id,
                workflow_version_id=run.workflow_version_id,
                workflow_id=workflow.id if workflow else None,
                workflow_name=workflow.name if workflow else None,
                status=run.status,
                input_text=run.input_text,
                final_output=run.final_output,
                created_at=run.created_at,
                completed_at=run.completed_at,
                eval_aggregate=float(run_eval_aggregate) if run_eval_aggregate is not None else None,
                eval_passed=run_eval_passed,
                guardrail_blocked=run_guardrail_blocked,
                session_id=run.session_id,
                tags=run.tags_json or [],
            )
        )
    return items


@router.get("/sessions")
def list_sessions(
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
    limit: int = Query(default=200, ge=10, le=1000),
):
    """Group recent runs into sessions (multi-turn threads) by session_id.

    Runs without a session_id are not sessions and are omitted. Sessions are
    ordered by most-recent activity.
    """
    rows = (
        db.query(models.WorkflowRun, models.Workflow.name)
        .join(models.WorkflowVersion, models.WorkflowRun.workflow_version_id == models.WorkflowVersion.id)
        .join(models.Workflow, models.WorkflowVersion.workflow_id == models.Workflow.id)
        .filter(models.Workflow.user_id == user_id, models.WorkflowRun.session_id.isnot(None))
        .order_by(models.WorkflowRun.created_at.desc())
        .limit(limit)
        .all()
    )
    sessions: dict[str, dict] = {}
    for run, workflow_name in rows:
        sid = run.session_id
        created = run.created_at.isoformat() if run.created_at else None
        entry = sessions.setdefault(
            sid,
            {
                "session_id": sid,
                "run_count": 0,
                "status_counts": {},
                "workflows": set(),
                "first_run_at": created,
                "last_run_at": created,
                "last_run_id": str(run.id),
            },
        )
        entry["run_count"] += 1
        entry["status_counts"][run.status] = entry["status_counts"].get(run.status, 0) + 1
        if workflow_name:
            entry["workflows"].add(workflow_name)
        if created:
            if entry["last_run_at"] is None or created > entry["last_run_at"]:
                entry["last_run_at"] = created
                entry["last_run_id"] = str(run.id)
            if entry["first_run_at"] is None or created < entry["first_run_at"]:
                entry["first_run_at"] = created
    result = sorted(sessions.values(), key=lambda s: s["last_run_at"] or "", reverse=True)
    for entry in result:
        entry["workflows"] = sorted(entry["workflows"])[:5]
    return {"sessions": result}


@router.post("", response_model=RunResponse)
async def create_run(
    payload: RunCreate,
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

    if payload.version_id:
        version = (
            db.query(models.WorkflowVersion)
            .filter(
                models.WorkflowVersion.id == payload.version_id,
                models.WorkflowVersion.workflow_id == payload.workflow_id,
            )
            .first()
        )
    else:
        version = (
            db.query(models.WorkflowVersion)
            .filter(models.WorkflowVersion.workflow_id == payload.workflow_id)
            .order_by(models.WorkflowVersion.version_number.desc())
            .first()
        )

    if not version:
        raise HTTPException(status_code=404, detail="Workflow version not found")

    if not (payload.input_text or "").strip():
        raise HTTPException(status_code=400, detail="input_text is required")

    from app.services.budgets import check_workflow_budget

    budget_breach = check_workflow_budget(db, workflow)
    if budget_breach:
        raise HTTPException(status_code=429, detail=budget_breach)

    try:
        validate_workflow_graph(version.graph_json)
    except GraphValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # In "inline" mode the authoritative concurrency signal is the in-memory
    # asyncio-task count; the (staleness-bounded) DB count is only needed as the
    # cross-process signal in "worker" mode. Counting raw pending/running rows
    # let orphaned runs (crash/restart/stuck scheduled fires) permanently exhaust
    # the limit and 429 every future run — see services/run_concurrency.
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

    if workflow_needs_gemini(version.graph_json) and not settings.google_api_key:
        raise HTTPException(
            status_code=400,
            detail="GOOGLE_API_KEY is not configured. Add it to .env to run LLM workflows.",
        )

    # Authoring-only pin/run-from-here validation (builder UI only; guarded off
    # the published invoke path, which never sets these). Validate against the
    # version graph before scheduling so a bad node id fails fast with a 400.
    if payload.pinned_outputs or payload.start_node_id:
        node_ids = {n.get("id") for n in (version.graph_json or {}).get("nodes", [])}
        if payload.start_node_id and payload.start_node_id not in node_ids:
            raise HTTPException(
                status_code=400,
                detail=f"start_node_id '{payload.start_node_id}' is not a node in this workflow.",
            )
        for pinned_id in (payload.pinned_outputs or {}):
            if pinned_id not in node_ids:
                raise HTTPException(
                    status_code=400,
                    detail=f"pinned_outputs references unknown node '{pinned_id}'.",
                )

    run = models.WorkflowRun(
        workflow_version_id=version.id,
        status="pending",
        input_text=payload.input_text,
        session_id=(payload.session_id or "").strip() or None,
        tags_json=(
            [t.strip() for t in payload.tags if isinstance(t, str) and t.strip()]
            if payload.tags
            else None
        ),
        # Persist pin/run-from-here so the worker process (which does not share
        # the API process's in-memory registry) can re-apply them. Never set by
        # /v1/invoke, which guards these params off the published path.
        authoring_overrides_json=(
            {
                "pinned_outputs": payload.pinned_outputs or {},
                "start_node_id": payload.start_node_id,
            }
            if (payload.pinned_outputs or payload.start_node_id)
            else None
        ),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    register_authoring_overrides(
        run.id,
        pinned_outputs=payload.pinned_outputs,
        start_node_id=payload.start_node_id,
    )

    if settings.run_execution_mode == "worker":
        pass
    else:
        schedule_run(run.id)

    return RunResponse(
        id=run.id,
        workflow_version_id=run.workflow_version_id,
        status=run.status,
        input_text=run.input_text,
        final_output=run.final_output,
        metrics_json=run.metrics_json,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        node_results=[],
    )


@router.get("/{run_id}", response_model=RunResponse)
def get_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    return _get_user_run(db, run_id, user_id)


@router.get("/{run_id}/llm-calls")
def get_run_llm_calls(
    run_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    _get_user_run(db, run_id, user_id)  # ownership check
    calls = (
        db.query(models.LlmCall)
        .filter(models.LlmCall.run_id == run_id)
        .order_by(models.LlmCall.created_at)
        .all()
    )
    return [
        {
            "id": str(c.id),
            "node_id": c.node_id,
            "model": c.model,
            "prompt_text": c.prompt_text,
            "completion_text": c.completion_text,
            "prompt_tokens": c.prompt_tokens,
            "completion_tokens": c.completion_tokens,
            "thinking_tokens": c.thinking_tokens,
            "total_tokens": c.total_tokens,
            "cost_usd": c.cost_usd,
            "latency_ms": c.latency_ms,
        }
        for c in calls
    ]


def _as_utc(dt: datetime) -> datetime:
    """Normalize DB-loaded (possibly naive) datetimes to aware UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.get("/{run_id}/timeline", response_model=RunTimelineResponse)
def get_run_timeline(
    run_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Node executions as a waterfall (offset+width spans) for canvas replay.

    Offsets are derived from each NodeResult's ``created_at`` (recorded at node
    completion) minus its ``latency_ms``, relative to the run's ``started_at``.
    Serialization only — no schema change (NodeResult.started_at was not added).
    """
    run = _get_user_run(db, run_id, user_id)

    results = (
        db.query(models.NodeResult)
        .filter(models.NodeResult.run_id == run_id)
        .order_by(models.NodeResult.created_at.asc())
        .all()
    )

    run_start = _as_utc(run.started_at) if run.started_at else None
    # Fallback anchor: if the run never recorded started_at, anchor at the first
    # node's derived start so offsets stay non-negative and relative.
    if run_start is None and results:
        first = results[0]
        first_latency = first.latency_ms or 0
        run_start = _as_utc(first.created_at) - timedelta(milliseconds=first_latency)

    # Label lookup from the version graph when available.
    label_by_node: dict[str, str] = {}
    graph = (run.version.graph_json if run.version else None) or {}
    for node in graph.get("nodes", []):
        data = node.get("data") or {}
        label = data.get("label")
        if node.get("id") and label:
            label_by_node[str(node["id"])] = label

    nodes: list[TimelineNode] = []
    for nr in results:
        latency = nr.latency_ms or 0
        completed_at = _as_utc(nr.created_at)
        node_start = completed_at - timedelta(milliseconds=latency)
        if run_start is not None:
            start_offset_ms = max(0, int((node_start - run_start).total_seconds() * 1000))
        else:
            start_offset_ms = 0
        nodes.append(
            TimelineNode(
                node_id=nr.node_id,
                node_type=nr.node_type,
                label=label_by_node.get(nr.node_id) or nr.node_label,
                status=nr.status,
                latency_ms=nr.latency_ms,
                start_offset_ms=start_offset_ms,
                duration_ms=max(0, latency),
            )
        )

    total_duration_ms = None
    if run.started_at and run.completed_at:
        total_duration_ms = max(
            0, int((_as_utc(run.completed_at) - _as_utc(run.started_at)).total_seconds() * 1000)
        )

    return RunTimelineResponse(
        run_id=run.id,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.completed_at,
        total_duration_ms=total_duration_ms,
        nodes=nodes,
    )


@router.get("/{run_id}/trace")
def get_run_trace(
    run_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Nested execution trace tree (Trust layer): node → llm_call / tool_call.

    Node parent spans are synthesized from NodeResults (same offset+width
    geometry as /timeline); their llm/tool child spans come from persisted
    RunSpan rows, nested by node_id and ordered chronologically. Lets the
    waterfall drill from a node into the agent's model + tool calls.
    """
    run = _get_user_run(db, run_id, user_id)

    results = (
        db.query(models.NodeResult)
        .filter(models.NodeResult.run_id == run_id)
        .order_by(models.NodeResult.created_at.asc())
        .all()
    )
    spans = (
        db.query(models.RunSpan)
        .filter(models.RunSpan.run_id == run_id)
        .all()
    )

    run_start = _as_utc(run.started_at) if run.started_at else None
    if run_start is None and results:
        first = results[0]
        run_start = _as_utc(first.created_at) - timedelta(milliseconds=first.latency_ms or 0)

    label_by_node: dict[str, str] = {}
    graph = (run.version.graph_json if run.version else None) or {}
    for node in graph.get("nodes", []):
        data = node.get("data") or {}
        if node.get("id") and data.get("label"):
            label_by_node[str(node["id"])] = data["label"]

    # Group child spans by node_id, ordered chronologically by captured start.
    children_by_node: dict[str, list] = {}
    for sp in spans:
        children_by_node.setdefault(sp.node_id or "", []).append(sp)
    for node_id in children_by_node:
        children_by_node[node_id].sort(
            key=lambda s: (s.attributes_json or {}).get("started_wall") or 0
        )

    def _child_dict(sp, node_offset_ms: int, base_wall: float | None) -> dict:
        attrs = dict(sp.attributes_json or {})
        started_wall = attrs.pop("started_wall", None)
        # Run-relative offset: node start + (child start − first child start).
        if started_wall is not None and base_wall is not None:
            offset = node_offset_ms + max(0, int((started_wall - base_wall) * 1000))
        else:
            offset = sp.offset_ms if sp.offset_ms is not None else node_offset_ms
        return {
            "id": str(sp.id),
            "parent_span_id": f"node:{sp.node_id}",
            "node_id": sp.node_id,
            "kind": sp.kind,
            "name": sp.name,
            "status": sp.status,
            "offset_ms": offset,
            "duration_ms": sp.duration_ms,
            "attributes": attrs or None,
            "tokens": sp.tokens_json,
            "cost_usd": sp.cost_usd,
            "children": [],
        }

    root_spans: list[dict] = []
    for nr in results:
        latency = nr.latency_ms or 0
        completed_at = _as_utc(nr.created_at)
        node_start = completed_at - timedelta(milliseconds=latency)
        node_offset = (
            max(0, int((node_start - run_start).total_seconds() * 1000)) if run_start else 0
        )
        kids = children_by_node.get(nr.node_id, [])
        base_wall = (
            (kids[0].attributes_json or {}).get("started_wall") if kids else None
        )
        node_cost = (nr.token_usage or {}).get("cost_usd") if nr.token_usage else None
        root_spans.append(
            {
                "id": f"node:{nr.node_id}",
                "parent_span_id": None,
                "node_id": nr.node_id,
                "kind": "node",
                "name": label_by_node.get(nr.node_id) or nr.node_label,
                "status": nr.status,
                "offset_ms": node_offset,
                "duration_ms": max(0, latency),
                "attributes": None,
                "tokens": nr.token_usage,
                "cost_usd": node_cost,
                "children": [_child_dict(sp, node_offset, base_wall) for sp in kids],
            }
        )

    total_duration_ms = None
    if run.started_at and run.completed_at:
        total_duration_ms = max(
            0, int((_as_utc(run.completed_at) - _as_utc(run.started_at)).total_seconds() * 1000)
        )

    return {
        "run_id": str(run.id),
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "total_duration_ms": total_duration_ms,
        "spans": root_spans,
    }


@router.get("/{run_id}/export")
def export_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    run = _get_user_run(db, run_id, user_id)
    workflow = run.version.workflow if run.version else None
    payload = {
        "run_id": str(run.id),
        "workflow_id": str(workflow.id) if workflow else None,
        "workflow_name": workflow.name if workflow else None,
        "status": run.status,
        "input_text": run.input_text,
        "final_output": run.final_output,
        "metrics_json": run.metrics_json,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "node_results": [
            {
                "node_id": nr.node_id,
                "node_label": nr.node_label,
                "node_type": nr.node_type,
                "status": nr.status,
                "output": nr.output,
                "evaluation_scores": nr.evaluation_scores,
                "guardrail_status": nr.guardrail_status,
                "latency_ms": nr.latency_ms,
                "token_usage": nr.token_usage,
            }
            for nr in (run.node_results or [])
        ],
    }
    return JSONResponse(
        content=payload,
        headers={"Content-Disposition": f'attachment; filename="run-{run_id}.json"'},
    )


@router.post("/{run_id}/approve")
def approve_run(
    run_id: UUID,
    payload: RunApprovalPayload,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    """Resume a run paused at a Human Approval node."""
    run = _get_user_run(db, run_id, user_id)
    if run.status != "awaiting_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Run is not awaiting approval (status: {run.status})",
        )

    metrics = dict(run.metrics_json or {})
    pending = metrics.get("pending_approval") if isinstance(metrics.get("pending_approval"), dict) else {}
    approval_node_id = pending.get("node_id") if isinstance(pending, dict) else None
    submit_approval(
        str(run_id),
        approved=payload.approved,
        comment=payload.comment or "",
        node_id=str(approval_node_id) if approval_node_id else None,
    )
    metrics.pop("pending_approval", None)
    metrics["approval_decision"] = {
        "approved": payload.approved,
        "comment": payload.comment,
        "node_id": approval_node_id,
    }
    run.metrics_json = metrics
    if payload.approved:
        run.status = "running"
    else:
        run.status = "failed"
        run.completed_at = run.completed_at or datetime.now(timezone.utc)
        run.final_output = payload.comment or "Approval rejected"
    db.commit()

    return {
        "status": "running" if payload.approved else "failed",
        "run_id": str(run_id),
        "approved": payload.approved,
    }


@router.delete("/{run_id}")
async def stop_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
):
    run = _get_user_run(db, run_id, user_id)
    if run.status not in {"pending", "running", "queued", "awaiting_approval"}:
        raise HTTPException(status_code=400, detail=f"Run is already {run.status}")

    # Always persist cancelled + cancel_requested so worker-mode completion
    # cannot clobber this with completed/failed. cancel_run is best-effort for
    # in-process tasks only.
    metrics = dict(run.metrics_json or {})
    metrics["cancel_requested"] = True
    metrics["cancelled"] = True
    run.metrics_json = metrics
    run.status = "cancelled"
    run.completed_at = run.completed_at or datetime.now(timezone.utc)
    db.commit()

    await cancel_run(str(run_id))

    return {"status": "cancelled", "run_id": str(run_id)}


_TERMINAL_RUN_STATES = {"completed", "failed", "cancelled"}


def _terminal_run_events(run: models.WorkflowRun) -> list[dict]:
    """Build synthetic SSE events mirroring the executor's terminal emissions.

    A client reconnecting after a run finished (or after the in-memory event
    TTL expired) would otherwise only receive heartbeats forever, since the
    executor's event broker is gone. Reconstruct the terminal event from the DB
    row so the stream ends cleanly.
    """
    run_key = str(run.id)
    if run.status == "completed":
        node_results = [
            {
                "node_id": nr.node_id,
                "node_label": nr.node_label,
                "node_type": nr.node_type,
                "status": nr.status,
                "output": nr.output,
                "evaluation_scores": nr.evaluation_scores,
                "guardrail_status": nr.guardrail_status,
                "latency_ms": nr.latency_ms,
            }
            for nr in (run.node_results or [])
        ]
        terminal = {
            "type": "run_completed",
            "run_id": run_key,
            "final_output": run.final_output,
            "metrics": run.metrics_json or {},
            "node_results": node_results,
        }
    elif run.status == "cancelled":
        terminal = {"type": "run_cancelled", "run_id": run_key}
    else:  # failed
        terminal = {
            "type": "run_failed",
            "run_id": run_key,
            "error": run.final_output or "Run failed",
        }
    return [terminal, {"type": "stream_end"}]


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
):
    db = SessionLocal()
    try:
        run = _get_user_run(db, run_id, user_id)
        terminal_events = (
            _terminal_run_events(run) if run.status in _TERMINAL_RUN_STATES else None
        )
    finally:
        db.close()

    async def event_generator():
        if terminal_events is not None:
            for event in terminal_events:
                yield f"data: {json.dumps(event, default=str)}\n\n"
            return
        async for event in stream_run_events(str(run_id)):
            yield f"data: {json.dumps(event, default=str)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")