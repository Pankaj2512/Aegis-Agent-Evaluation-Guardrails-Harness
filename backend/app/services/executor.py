from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Callable

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.db import models
from app.db.database import SessionLocal
from app.logging_config import log_context
from app.services.approval_service import HumanApprovalDenied, clear_approval_state
from app.services.async_tasks import schedule_task
from app.services.compiler import compile_workflow
from app.services.kb_cache import load_workflow_kb_documents
from app.services.observability_rollups import record_run_rollup
from app.services.persistent_memory import flush_memory_writes, load_workflow_memory, merge_memory_into_context
from app.services.workflow_context import WorkflowContext
from app.services.eval import EvalThresholdBlockedError, compute_aggregate_score
from app.services.eval_preset_service import enrich_graph_eval_presets
from app.services.eval_runner import run_parallel_evaluations
from app.services.observability_events import broadcast_observability_event
from app.services.quality_alerts import quality_webhook_for_run
from app.services.token_tracker import TokenTrackerPlugin
from app.services.trace_plugin import TracePlugin
from app.services.guardrail_policy_plugin import GuardrailPolicyPlugin
from app.services.quality_metrics import apply_eval_threshold
from app.services.guardrail import GuardrailBlockedError, GuardrailResult
from app.services.tracing import NodeSpanTracker, get_trace_id, workflow_run_span
from app.services.webhook import dispatch_webhook

import logging

logger = logging.getLogger("aegis.executor")

class _RunEventBroker:
    """Fan out run events to every SSE subscriber of a single run.

    Each subscriber gets its own queue (mirroring
    app/services/observability_events.py) so concurrent stream clients no longer
    steal events from one another. The broker also retains the terminal event
    (stream_end / run_*) so a subscriber that attaches just before cleanup still
    observes stream termination.
    """

    __slots__ = ("subscribers", "terminated")

    def __init__(self) -> None:
        self.subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self.terminated = False

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
        self.subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self.subscribers.discard(queue)

    def broadcast(self, event: dict[str, Any]) -> None:
        if event.get("type") == "stream_end":
            self.terminated = True
        for queue in list(self.subscribers):
            _enqueue_event(queue, event)


_run_events: dict[str, _RunEventBroker] = {}
_active_tasks: dict[str, asyncio.Task[None]] = {}
_cleanup_tasks: set[asyncio.Task[None]] = set()
_STREAM_EVENT_TTL_SECONDS = 120

# Authoring-only run overrides (pin outputs + run-from-here), keyed by run id.
# Populated ONLY by the authenticated run-create path and consumed once by
# execute_run. Never populated by the published invoke path — guarding pin/
# run-from-here to the builder. Kept in memory so it never reaches the DB.
_authoring_overrides: dict[str, dict[str, Any]] = {}


def register_authoring_overrides(
    run_id: uuid.UUID,
    *,
    pinned_outputs: dict[str, Any] | None,
    start_node_id: str | None,
) -> None:
    """Attach authoring-only pin/run-from-here params to a pending run."""
    if not pinned_outputs and not start_node_id:
        return
    _authoring_overrides[str(run_id)] = {
        "pinned_outputs": pinned_outputs or {},
        "start_node_id": start_node_id,
    }


def _as_utc(dt: datetime) -> datetime:
    """Normalize DB-loaded (possibly naive) datetimes to aware UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _enqueue_event(event_queue: asyncio.Queue[dict[str, Any]], event: dict[str, Any]) -> None:
    """Enqueue an event on a single subscriber queue; drop oldest when full."""
    try:
        event_queue.put_nowait(event)
    except asyncio.QueueFull:
        try:
            event_queue.get_nowait()
        except asyncio.QueueEmpty:
            pass
        try:
            event_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning(
                "Dropped run event because queue is full",
                extra={"event_type": event.get("type")},
            )


def _put_run_event(broker: _RunEventBroker, event: dict[str, Any]) -> None:
    """Broadcast a run event to every subscriber of the run."""
    broker.broadcast(event)


def _ensure_api_key() -> None:
    from app.config import configure_runtime_env

    configure_runtime_env()


def _json_default(value: Any) -> Any:
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return value.decode("utf-8", errors="replace")
    return str(value)


def _normalize_text_part(text: str) -> str:
    stripped = text.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] == '"':
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, str):
                return parsed
        except json.JSONDecodeError:
            pass
    return stripped


def _extract_text_parts(value: Any) -> str | None:
    if not hasattr(value, "parts"):
        return None

    texts: list[str] = []
    for part in value.parts:
        text = getattr(part, "text", None)
        if text:
            texts.append(_normalize_text_part(str(text)))
            continue

        function_call = getattr(part, "function_call", None)
        if not function_call:
            continue
        args = getattr(function_call, "args", None) or {}
        if isinstance(args, dict) and args.get("response") is not None:
            texts.append(str(args["response"]))

    return "\n".join(texts) if texts else None


def _stringify_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return _json_default(value)

    part_text = _extract_text_parts(value)
    if part_text:
        return part_text

    if hasattr(value, "text") and value.text:
        return str(value.text)

    if hasattr(value, "model_dump_json"):
        try:
            return value.model_dump_json()
        except Exception:
            pass

    if hasattr(value, "model_dump"):
        try:
            return json.dumps(value.model_dump(mode="json"), default=_json_default)
        except TypeError:
            return json.dumps(value.model_dump(), default=_json_default)

    if isinstance(value, (dict, list)):
        return json.dumps(value, default=_json_default)

    text = str(value)
    if text.startswith("parts=[Part(") and "text=" in text:
        match = re.search(r"text='([^']*)'|text=\"([^\"]*)\"", text)
        if match:
            return match.group(1) or match.group(2)
    return text


def _extract_text_from_event(event: Any) -> str | None:
    output = _stringify_value(getattr(event, "output", None))
    if output:
        return output
    if hasattr(event, "message") and event.message:
        return _stringify_value(event.message)
    return _stringify_value(getattr(event, "content", None))


def _extract_token_usage(event: Any) -> dict | None:
    usage = getattr(event, "usage_metadata", None)
    if not usage:
        return None
    return {
        "prompt_tokens": getattr(usage, "prompt_token_count", None),
        "completion_tokens": getattr(usage, "candidates_token_count", None),
        "total_tokens": getattr(usage, "total_token_count", None),
    }


def _resolve_node_id(
    author: str | None,
    metadata: dict[str, dict],
    author_lookup: dict[str, str],
    node_path: str | None = None,
) -> str | None:
    # ADK 2.x attributes child events to the root workflow (event.author is
    # always the workflow name); the executing node lives in
    # event.node_info.path, formatted "wf@1/node_name@2". Try path segments
    # leaf-first, then fall back to the author for older event shapes.
    candidates: list[str] = []
    if node_path:
        for segment in reversed(node_path.split("/")):
            name = segment.split("@", 1)[0]
            if name:
                candidates.append(name)
    if author:
        candidates.append(author)
    for name in candidates:
        if name in author_lookup:
            return author_lookup[name]
        for node_id, meta in metadata.items():
            adk_name = meta.get("adk_name", "")
            if name == adk_name or name.endswith(f"_{node_id}"):
                return node_id
    return None


async def _commit_db(db: Session) -> None:
    await asyncio.to_thread(db.commit)


def _run_session() -> Session:
    # expire_on_commit=False: run objects (with joinedloaded version/workflow)
    # are read after commit+close; expiring them would trigger detached-instance
    # lazy loads.
    return SessionLocal(expire_on_commit=False)


def _load_run(session: Session, run_id: uuid.UUID) -> models.WorkflowRun | None:
    return (
        session.query(models.WorkflowRun)
        .options(
            joinedload(models.WorkflowRun.version).joinedload(models.WorkflowVersion.workflow)
        )
        .filter(models.WorkflowRun.id == run_id)
        .first()
    )


async def _with_run_session(
    run_id: uuid.UUID,
    fn: Callable[[Session, models.WorkflowRun], Any],
    *,
    commit: bool = True,
) -> Any:
    def _work() -> Any:
        session = _run_session()
        try:
            run = _load_run(session, run_id)
            if not run:
                return None
            result = fn(session, run)
            if commit:
                session.commit()
            return result
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return await asyncio.to_thread(_work)


async def _read_run_status(run_id: uuid.UUID) -> str | None:
    def _read() -> str | None:
        session = SessionLocal()
        try:
            row = (
                session.query(models.WorkflowRun.status)
                .filter(models.WorkflowRun.id == run_id)
                .first()
            )
            return row[0] if row else None
        finally:
            session.close()

    return await asyncio.to_thread(_read)


async def _consume_with_timeout(run_id: uuid.UUID, coro: Any) -> None:
    """Run the event-consumption coroutine under the run timeout, but do NOT
    count time spent paused at a human-approval node against that budget.

    A run parked in ``awaiting_approval`` may legitimately wait up to
    ``approval_timeout_seconds`` (>> ``run_timeout_seconds``); the previous
    single ``asyncio.wait_for`` killed it after ``run_timeout_seconds``. Here we
    accumulate only "active" (non-awaiting) elapsed time and re-arm the deadline
    while the run is awaiting approval, raising ``asyncio.TimeoutError`` only
    when active work exceeds the budget.
    """
    budget = float(settings.run_timeout_seconds)
    poll = 1.0
    task = asyncio.ensure_future(coro)
    active_elapsed = 0.0
    try:
        while True:
            done, _pending = await asyncio.wait({task}, timeout=poll)
            if task in done:
                task.result()  # re-raise any exception from _consume_events
                return
            # Task still running: only charge this interval if the run is not
            # currently paused awaiting human approval.
            status = await _read_run_status(run_id)
            if status != "awaiting_approval":
                active_elapsed += poll
            if active_elapsed >= budget:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                raise asyncio.TimeoutError()
    finally:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


async def _notify_observability(
    run: models.WorkflowRun,
    event_type: str,
    *,
    trace_id: str | None = None,
) -> None:
    workflow = run.version.workflow if run.version else None
    if not workflow:
        return
    metrics = run.metrics_json or {}
    payload: dict[str, Any] = {
        "type": event_type,
        "run_id": str(run.id),
        "workflow_id": str(workflow.id),
        "workflow_name": workflow.name,
        "status": run.status,
        "eval_aggregate": metrics.get("eval_aggregate"),
        "eval_passed": metrics.get("eval_passed"),
        "guardrail_blocked": bool(metrics.get("guardrail_blocked")),
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "input_text": (run.input_text or "")[:200],
    }
    resolved_trace_id = trace_id or metrics.get("trace_id")
    if resolved_trace_id:
        payload["trace_id"] = resolved_trace_id
    if run.started_at:
        end = _as_utc(run.completed_at or datetime.now(timezone.utc))
        payload["latency_ms"] = max(0, int((end - _as_utc(run.started_at)).total_seconds() * 1000))
    await broadcast_observability_event(str(workflow.user_id), payload)


def _parse_evaluation_scores(text: str | None, weights: dict | None = None) -> dict | None:
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            scores = {
                "faithfulness": parsed.get("faithfulness"),
                "helpfulness": parsed.get("helpfulness"),
                "relevance": parsed.get("relevance"),
                "toxicity": parsed.get("toxicity"),
                "reasoning": parsed.get("reasoning", ""),
            }
            aggregate = compute_aggregate_score(scores, weights)
            if aggregate is not None:
                scores["aggregate_score"] = aggregate
            return scores
    except json.JSONDecodeError:
        return {"raw": text}
    return None


def _parse_guardrail_status(
    node_id: str,
    text: str | None,
    guardrail_results: dict[str, GuardrailResult],
) -> tuple[str | None, str | None]:
    gr = guardrail_results.get(node_id)
    if gr:
        output = gr.output_override or gr.message
        if gr.severity == "warn":
            return ("warned", output)
        return ("passed" if gr.passed else "failed", output)
    if not text:
        return None, None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict) and "passed" in parsed:
            return ("passed" if parsed["passed"] else "failed", parsed.get("message", text))
    except json.JSONDecodeError:
        pass
    lowered = text.lower()
    if "blocked" in lowered or "failed" in lowered:
        return "failed", text
    if "passed" in lowered:
        return "passed", text
    return None, text


def _merge_run_metrics(run: models.WorkflowRun, updates: dict[str, Any]) -> dict[str, Any]:
    """Merge into existing metrics_json so keys like trace_id survive terminal writes."""
    metrics = dict(run.metrics_json or {})
    metrics.update(updates)
    run.metrics_json = metrics
    return metrics


def _is_cancel_requested(run: models.WorkflowRun) -> bool:
    if run.status == "cancelled":
        return True
    metrics = run.metrics_json or {}
    return bool(metrics.get("cancel_requested") or metrics.get("cancelled"))


async def _schedule_run_event_cleanup(run_key: str) -> None:
    await asyncio.sleep(_STREAM_EVENT_TTL_SECONDS)
    _run_events.pop(run_key, None)


async def _run_workflow(
    run_id: uuid.UUID,
    graph_json: dict,
    event_queue: _RunEventBroker,
    *,
    input_text: str,
    workflow_user_id: uuid.UUID | None,
    workflow_id: uuid.UUID | None,
    error_context: dict[str, Any] | None = None,
    authoring_overrides: dict[str, Any] | None = None,
) -> None:
    guardrail_results: dict[str, GuardrailResult] = {}

    def on_guardrail(node_id: str, result: GuardrailResult) -> None:
        guardrail_results[node_id] = result

    workflow_context = WorkflowContext.from_input(input_text)

    # Authoring-only pin/run-from-here: seed pinned upstream outputs into the
    # context and prune the graph to begin at start_node_id. Never reached from
    # the published invoke path (overrides are only registered on run-create).
    if authoring_overrides:
        from app.services.run_authoring import (
            prune_graph_for_start,
            seed_pinned_outputs,
        )

        pinned_outputs = authoring_overrides.get("pinned_outputs") or {}
        start_node_id = authoring_overrides.get("start_node_id")
        if pinned_outputs:
            seed_pinned_outputs(workflow_context, graph_json, pinned_outputs)
        if start_node_id:
            graph_json = prune_graph_for_start(graph_json, start_node_id, pinned_outputs)

    context_ref = workflow_context.to_dict()
    # Preserve pinned last_output across the trigger passthrough when run-from-here.
    if authoring_overrides and (authoring_overrides.get("pinned_outputs") or {}):
        last = context_ref.get("last_output")
        if last is not None:
            context_ref["_seeded_last_output"] = last
    run_key = str(run_id)
    context_ref["_run_id"] = run_key
    if workflow_id is not None:
        context_ref["_user_id"] = str(workflow_user_id) if workflow_user_id else None
        context_ref["_workflow_id"] = str(workflow_id)

        def _load_memory_and_kb() -> tuple[Any, Any]:
            # Whole session unit of work stays inside one thread; only plain
            # values escape (SQLAlchemy sessions are not thread-safe to share).
            setup_db = _run_session()
            try:
                persisted = load_workflow_memory(setup_db, workflow_id)
                kb_documents = load_workflow_kb_documents(setup_db, workflow_id)
                return persisted, kb_documents
            finally:
                setup_db.close()

        persisted, kb_documents = await asyncio.to_thread(_load_memory_and_kb)
        merge_memory_into_context(context_ref, persisted)
        context_ref["_kb_documents"] = kb_documents

    async def _emit(event: dict[str, Any]) -> None:
        _put_run_event(event_queue, event)

    async def _mark_awaiting_approval(run_id: str, node_id: str, review: str) -> None:
        def _update() -> dict[str, Any] | None:
            session = SessionLocal()
            try:
                db_run = (
                    session.query(models.WorkflowRun)
                    .filter(models.WorkflowRun.id == uuid.UUID(run_id))
                    .with_for_update()
                    .first()
                )
                if not db_run:
                    return None
                db_run.status = "awaiting_approval"
                metrics = dict(db_run.metrics_json or {})
                metrics["pending_approval"] = {
                    "node_id": node_id,
                    "review": review,
                }
                db_run.metrics_json = metrics
                session.commit()
                # Payload for the observability stream (triage should not stay "running").
                wf = (
                    session.query(models.Workflow)
                    .join(models.WorkflowVersion)
                    .filter(models.WorkflowVersion.id == db_run.workflow_version_id)
                    .first()
                )
                return {
                    "type": "run_updated",
                    "run_id": str(db_run.id),
                    "workflow_id": str(wf.id) if wf else None,
                    "workflow_name": wf.name if wf else None,
                    "status": "awaiting_approval",
                    "created_at": db_run.created_at.isoformat() if db_run.created_at else None,
                    "input_text": (db_run.input_text or "")[:200],
                }
            finally:
                session.close()

        payload = await asyncio.to_thread(_update)
        if payload:
            try:
                user_id = workflow_user_id
                if user_id is not None:
                    await broadcast_observability_event(str(user_id), payload)
            except Exception:  # noqa: BLE001 — never block approval on SSE fanout
                logger.exception("Failed to broadcast awaiting_approval observability event")

    context_ref["_emit"] = _emit
    context_ref["_mark_awaiting_approval"] = _mark_awaiting_approval

    if workflow_user_id is not None:

        def _enrich_graph(current_graph: dict) -> dict:
            # Single-thread unit of work; returns a plain enriched graph dict.
            preset_db = _run_session()
            try:
                enriched = enrich_graph_eval_presets(current_graph, preset_db, workflow_user_id)
                from app.api.guardrail_policies import enrich_graph_guardrail_policies

                return enrich_graph_guardrail_policies(enriched, preset_db, workflow_user_id)
            finally:
                preset_db.close()

        graph_json = await asyncio.to_thread(_enrich_graph, graph_json)

    workflow, metadata, author_lookup = compile_workflow(
        graph_json,
        on_guardrail_result=on_guardrail,
        context_ref=context_ref,
    )

    session_service = InMemorySessionService()
    token_tracker = TokenTrackerPlugin()
    trace_plugin = TracePlugin()
    guardrail_policy_plugin = await asyncio.to_thread(
        _resolve_workflow_guardrail_plugin, graph_json, workflow_user_id
    )
    plugins: list[Any] = [token_tracker, trace_plugin]
    if guardrail_policy_plugin is not None:
        plugins.append(guardrail_policy_plugin)
    runner = Runner(
        app_name="aegis",
        node=workflow,
        session_service=session_service,
        auto_create_session=True,
        plugins=plugins,
    )

    try:
        await _run_workflow_body(
            run_id,
            event_queue,
            guardrail_results=guardrail_results,
            workflow_context=workflow_context,
            context_ref=context_ref,
            run_key=run_key,
            metadata=metadata,
            author_lookup=author_lookup,
            runner=runner,
            input_text=input_text,
            token_tracker=token_tracker,
            trace_plugin=trace_plugin,
            guardrail_policy_plugin=guardrail_policy_plugin,
            error_context=error_context,
        )
    finally:
        memory_db = _run_session()
        try:
            try:
                flush_memory_writes(memory_db, context_ref)
            except Exception:
                logger.exception(
                    "Failed to flush workflow memory",
                    extra={"run_id": run_key},
                )

                def _mark_memory_flush_failed() -> None:
                    session = SessionLocal()
                    try:
                        db_run = session.query(models.WorkflowRun).filter(
                            models.WorkflowRun.id == run_id
                        ).first()
                        if not db_run:
                            return
                        metrics = dict(db_run.metrics_json or {})
                        metrics["memory_flush_failed"] = True
                        db_run.metrics_json = metrics
                        session.commit()
                    finally:
                        session.close()

                await asyncio.to_thread(_mark_memory_flush_failed)
        finally:
            memory_db.close()


def _resolve_workflow_guardrail_plugin(
    graph_json: dict, user_id: uuid.UUID | None
) -> GuardrailPolicyPlugin | None:
    """Build a workflow-level guardrail plugin from the trigger node's config.

    The workflow-wide policy lives on the trigger node's data
    (``workflowGuardrailPolicyId`` + ``workflowGuardrailMode``) so it round-trips
    with the graph and needs no schema change. Returns ``None`` when unset or the
    referenced policy is missing.
    """
    policy_id: Any = None
    mode = "both"
    for node in graph_json.get("nodes", []) or []:
        data = node.get("data") or {}
        if data.get("nodeType") == "trigger":
            policy_id = data.get("workflowGuardrailPolicyId")
            mode = data.get("workflowGuardrailMode") or "both"
            break
    if not policy_id or user_id is None:
        return None
    try:
        pid = uuid.UUID(str(policy_id))
    except (ValueError, TypeError):
        return None

    db = SessionLocal()
    try:
        policy = (
            db.query(models.GuardrailPolicy)
            .filter(
                models.GuardrailPolicy.id == pid,
                models.GuardrailPolicy.user_id == user_id,
            )
            .first()
        )
        if not policy or not policy.rules_json:
            return None
        return GuardrailPolicyPlugin(policy.rules_json, mode=mode, policy_name=policy.name)
    finally:
        db.close()


async def _run_workflow_body(
    run_id: uuid.UUID,
    event_queue: _RunEventBroker,
    *,
    guardrail_results: dict[str, GuardrailResult],
    workflow_context: WorkflowContext,
    context_ref: dict[str, Any],
    run_key: str,
    metadata: dict[str, dict],
    author_lookup: dict[str, str],
    runner: Runner,
    input_text: str,
    token_tracker: TokenTrackerPlugin | None = None,
    trace_plugin: TracePlugin | None = None,
    guardrail_policy_plugin: GuardrailPolicyPlugin | None = None,
    error_context: dict[str, Any] | None = None,
) -> None:
    node_spans = NodeSpanTracker()
    started_nodes: dict[str, float] = {}
    completed_nodes: set[str] = set()
    node_outputs: dict[str, str] = {}
    eval_score_rows: list[dict] = []
    failed_guardrails: list[str] = []
    guardrail_events: list[dict] = []
    total_tokens = 0
    final_output: str | None = None

    async def _persist_node_result(
        matched_node_id: str,
        *,
        text: str | None,
        token_usage: dict | None,
        status: str = "completed",
    ) -> None:
        nonlocal final_output

        if matched_node_id in completed_nodes:
            return

        started_at = started_nodes.setdefault(matched_node_id, time.time())
        latency_ms = int((time.time() - started_at) * 1000)
        meta = metadata[matched_node_id]

        # A node that failed but carried an error branch was routed instead of
        # raising; the wrapper flagged it here so telemetry stays honest.
        if status == "completed" and matched_node_id in (context_ref.get("_error_routed") or {}):
            status = "failed"

        node_result = models.NodeResult(
            run_id=run_id,
            node_id=matched_node_id,
            node_type=meta["type"],
            node_label=meta["label"],
            status=status,
            output=text,
            latency_ms=latency_ms,
            token_usage=token_usage,
        )

        if meta.get("is_guardrail"):
            guardrail_status, output = _parse_guardrail_status(
                matched_node_id, text, guardrail_results
            )
            node_result.guardrail_status = guardrail_status
            if output:
                node_result.output = output
            # Only hard failures feed failed_guardrails; warn/rewrite/fallback
            # are non-blocking and tracked via guardrail_events alone.
            if guardrail_status == "failed":
                failed_guardrails.append(matched_node_id)
            guardrail_events.append(
                {
                    "node_id": matched_node_id,
                    "node_label": meta["label"],
                    "status": guardrail_status or "unknown",
                    "message": output or "",
                    "mode": meta.get("guardrail_mode"),
                    "guardrail_type": meta.get("guardrail_type"),
                    "fail_behavior": meta.get("fail_behavior"),
                }
            )

        if meta.get("is_evaluation") and not meta.get("eval_deferred"):
            node_result.evaluation_scores = _parse_evaluation_scores(
                text,
                meta.get("score_weights"),
            )
            if node_result.evaluation_scores:
                row = {
                    "node_id": matched_node_id,
                    "node_label": meta["label"],
                    **node_result.evaluation_scores,
                }
                eval_score_rows.append(row)
                threshold = meta.get("eval_threshold")
                aggregate = row.get("aggregate_score")
                fail_behavior = meta.get("eval_fail_behavior", "none")
                if (
                    threshold is not None
                    and aggregate is not None
                    and float(aggregate) < float(threshold)
                ):
                    row["passed"] = False
                    row["threshold"] = threshold
                    if fail_behavior == "block":
                        raise EvalThresholdBlockedError(
                            f"Eval score {aggregate} below threshold {threshold}",
                            matched_node_id,
                            float(aggregate),
                        )
                    if fail_behavior == "warn":
                        row["warned"] = True

        # Mark complete only after the eval-threshold check above (which may
        # raise EvalThresholdBlockedError) and after the row is persisted, so a
        # blocking eval node is re-persisted with status "failed" by the handler
        # instead of being silently skipped by the `in completed_nodes` guard.
        await _with_run_session(run_id, lambda session, _run: session.add(node_result))
        completed_nodes.add(matched_node_id)

        node_spans.end(
            matched_node_id,
            status=status,
            latency_ms=latency_ms,
            guardrail_status=node_result.guardrail_status,
        )

        _put_run_event(event_queue,
            {
                "type": "node_completed",
                "node_id": matched_node_id,
                "node_label": meta["label"],
                "status": status,
                "output": node_result.output,
                "evaluation_scores": node_result.evaluation_scores,
                "guardrail_status": node_result.guardrail_status,
                "latency_ms": latency_ms,
            }
        )

    async def _consume_events() -> None:
        nonlocal final_output, total_tokens

        try:
            async for event in runner.run_async(
                user_id="aegis-user",
                session_id=str(uuid.uuid4()),
                new_message=types.Content(parts=[types.Part(text=input_text)]),
            ):
                author = getattr(event, "author", None) or "workflow"
                text = _extract_text_from_event(event)
                token_usage = _extract_token_usage(event)
                node_path = getattr(getattr(event, "node_info", None), "path", None)
                matched_node_id = _resolve_node_id(author, metadata, author_lookup, node_path)

                if not matched_node_id:
                    continue

                if matched_node_id not in started_nodes:
                    started_nodes[matched_node_id] = time.time()
                    node_meta = metadata[matched_node_id]
                    # Record the currently-executing node so the run's broad
                    # exception handler can report which node blew up
                    # (improves assist.explain_run).
                    if error_context is not None:
                        error_context["last_node_id"] = matched_node_id
                        error_context["last_node_type"] = node_meta["type"]
                        error_context["last_node_label"] = node_meta["label"]
                    node_spans.start(
                        matched_node_id,
                        node_meta["type"],
                        node_meta["label"],
                    )
                    _put_run_event(event_queue,
                        {
                            "type": "node_started",
                            "node_id": matched_node_id,
                            "node_label": node_meta["label"],
                        }
                    )

                if text:
                    node_outputs[matched_node_id] = text
                    final_output = text
                    # Run-from-here: the trigger passthrough emits the pinned
                    # seed downstream, but the wrapper already recorded the
                    # trigger's honest step output (raw run input). Don't clobber
                    # it here — keep {{steps.<trigger>.output}} truthful.
                    seeded_trigger = (
                        metadata[matched_node_id]["type"] == "trigger"
                        and context_ref.get("_seeded_last_output") is not None
                    )
                    if not seeded_trigger:
                        workflow_context.record_step(
                            matched_node_id,
                            text,
                            label=metadata[matched_node_id]["label"],
                            node_type=metadata[matched_node_id]["type"],
                        )

                if token_usage and token_usage.get("total_tokens"):
                    total_tokens += int(token_usage["total_tokens"] or 0)

                is_complete = bool(getattr(event, "turn_complete", False) or text)
                if is_complete:
                    await _persist_node_result(
                        matched_node_id,
                        text=text,
                        token_usage=token_usage,
                    )
        except EvalThresholdBlockedError as exc:
            if exc.node_id not in completed_nodes:
                await _persist_node_result(
                    exc.node_id,
                    text=str(exc),
                    token_usage=None,
                    status="failed",
                )
            metrics_payload = {
                "eval_scores": eval_score_rows,
                "eval_aggregate": exc.aggregate,
                "eval_passed": False,
                "eval_threshold_blocked": True,
                "failed_eval_node": exc.node_id,
                "workflow_context": workflow_context.snapshot_for_metrics(),
            }

            def _fail_eval(session: Session, run: models.WorkflowRun) -> models.WorkflowRun:
                if _is_cancel_requested(run):
                    _merge_run_metrics(run, metrics_payload)
                    return run
                run.status = "failed"
                run.final_output = f"Eval threshold not met at node {exc.node_id}: {exc}"
                run.completed_at = datetime.now(timezone.utc)
                _merge_run_metrics(run, metrics_payload)
                return run

            failed_run = await _with_run_session(run_id, _fail_eval)
            workflow = failed_run.version.workflow if failed_run and failed_run.version else None
            quality_webhook_for_run(None, failed_run, workflow)
            raise

        except GuardrailBlockedError as exc:
            if exc.node_id not in completed_nodes:
                gr = guardrail_results.get(exc.node_id)
                await _persist_node_result(
                    exc.node_id,
                    text=gr.message if gr else str(exc),
                    token_usage=None,
                    status="failed",
                )
            gr = guardrail_results.get(exc.node_id)
            meta = metadata.get(exc.node_id, {})
            metrics_payload = {
                "failed_guardrails": [exc.node_id],
                "guardrail_blocked": True,
                "guardrail_events": [
                    {
                        "node_id": exc.node_id,
                        "node_label": meta.get("label", exc.node_id),
                        "status": "failed",
                        "message": gr.message if gr else str(exc),
                        "mode": meta.get("guardrail_mode"),
                        "guardrail_type": meta.get("guardrail_type"),
                        "fail_behavior": meta.get("fail_behavior"),
                    }
                ],
            }

            def _fail_guardrail(session: Session, run: models.WorkflowRun) -> models.WorkflowRun:
                if _is_cancel_requested(run):
                    _merge_run_metrics(run, metrics_payload)
                    return run
                run.status = "failed"
                run.final_output = f"Guardrail blocked at node {exc.node_id}: {exc}"
                run.completed_at = datetime.now(timezone.utc)
                _merge_run_metrics(run, metrics_payload)
                return run

            failed_run = await _with_run_session(run_id, _fail_guardrail)
            workflow = failed_run.version.workflow if failed_run and failed_run.version else None
            quality_webhook_for_run(None, failed_run, workflow)
            raise

    await _consume_with_timeout(run_id, _consume_events())

    deferred_specs = [
        (node_id, metadata[node_id], node_outputs.get(node_id, ""))
        for node_id, meta in metadata.items()
        if meta.get("is_evaluation") and meta.get("eval_deferred")
    ]
    deferred_eval_usage: dict[str, dict[str, Any]] = {}
    if deferred_specs:
        parallel_results = await run_parallel_evaluations(deferred_specs, request_context=input_text)
        for node_id, scores, error in parallel_results:
            meta = metadata[node_id]
            if scores:
                eval_usage = scores.pop("_token_usage", None)
                if eval_usage:
                    deferred_eval_usage[node_id] = eval_usage
            if error or not scores:
                _put_run_event(event_queue,
                    {
                        "type": "node_completed",
                        "node_id": node_id,
                        "node_label": meta["label"],
                        "status": "failed",
                        "output": error or "Eval failed",
                        "evaluation_scores": None,
                        "guardrail_status": None,
                        "latency_ms": None,
                    }
                )
                continue

            row = {
                "node_id": node_id,
                "node_label": meta["label"],
                **scores,
            }
            eval_score_rows.append(row)
            threshold = meta.get("eval_threshold")
            aggregate = row.get("aggregate_score")
            fail_behavior = meta.get("eval_fail_behavior", "none")
            if (
                threshold is not None
                and aggregate is not None
                and float(aggregate) < float(threshold)
            ):
                row["passed"] = False
                row["threshold"] = threshold
                if fail_behavior == "warn":
                    row["warned"] = True
                if fail_behavior == "block":
                    def _block_deferred(session: Session, run: models.WorkflowRun) -> models.WorkflowRun:
                        existing = (
                            session.query(models.NodeResult)
                            .filter(
                                models.NodeResult.run_id == run.id,
                                models.NodeResult.node_id == node_id,
                            )
                            .first()
                        )
                        if existing:
                            existing.evaluation_scores = scores
                            existing.status = "failed"
                            existing.output = f"Eval score {aggregate} below threshold {threshold}"
                        metrics_payload = {
                            "eval_scores": eval_score_rows,
                            "eval_aggregate": aggregate,
                            "eval_passed": False,
                            "eval_threshold_blocked": True,
                            "failed_eval_node": node_id,
                            "workflow_context": workflow_context.snapshot_for_metrics(),
                        }
                        if _is_cancel_requested(run):
                            _merge_run_metrics(run, metrics_payload)
                            return run
                        run.status = "failed"
                        run.final_output = (
                            f"Eval threshold not met at node {node_id}: "
                            f"score {aggregate} < {threshold}"
                        )
                        run.completed_at = datetime.now(timezone.utc)
                        _merge_run_metrics(run, metrics_payload)
                        return run

                    blocked_run = await _with_run_session(run_id, _block_deferred)
                    workflow = blocked_run.version.workflow if blocked_run and blocked_run.version else None
                    quality_webhook_for_run(None, blocked_run, workflow)
                    raise EvalThresholdBlockedError(
                        f"Eval score {aggregate} below threshold {threshold}",
                        node_id,
                        float(aggregate),
                    )

            output_text = json.dumps(scores, default=_json_default)

            def _save_deferred(session: Session, run: models.WorkflowRun) -> str:
                existing = (
                    session.query(models.NodeResult)
                    .filter(
                        models.NodeResult.run_id == run.id,
                        models.NodeResult.node_id == node_id,
                    )
                    .first()
                )
                if existing:
                    existing.evaluation_scores = scores
                    existing.output = output_text
                    return existing.output or output_text
                session.add(
                    models.NodeResult(
                        run_id=run.id,
                        node_id=node_id,
                        node_type=meta["type"],
                        node_label=meta["label"],
                        status="completed",
                        output=output_text,
                        evaluation_scores=scores,
                    )
                )
                return output_text

            saved_output = await _with_run_session(run_id, _save_deferred)
            _put_run_event(event_queue,
                {
                    "type": "node_completed",
                    "node_id": node_id,
                    "node_label": meta["label"],
                    "status": "completed",
                    "output": saved_output,
                    "evaluation_scores": scores,
                    "guardrail_status": None,
                    "latency_ms": None,
                }
            )

    # Fold plugin-captured token usage into node results and run totals.
    # (ADK 2.x strips usage_metadata from propagated events, so the event loop
    # above never sees token counts — the model-callback plugin does.)
    node_usage: dict[str, dict[str, Any]] = {}

    def _merge_usage(node_id: str, row: dict[str, Any]) -> None:
        existing = node_usage.get(node_id)
        if not existing:
            node_usage[node_id] = dict(row)
            return
        for key in ("prompt_tokens", "completion_tokens", "thinking_tokens", "total_tokens", "calls"):
            existing[key] = (existing.get(key) or 0) + (row.get(key) or 0)
        if row.get("cost_usd") is not None:
            existing["cost_usd"] = round((existing.get("cost_usd") or 0) + row["cost_usd"], 6)

    if token_tracker and token_tracker.usage_by_agent:
        from app.config import settings as _settings

        for agent_name, row in token_tracker.usage_with_cost(_settings.gemini_model).items():
            node_id = _resolve_node_id(agent_name, metadata, author_lookup)
            if not node_id:
                continue
            _merge_usage(node_id, row)
    for node_id, row in deferred_eval_usage.items():
        _merge_usage(node_id, row)
    for node_id, row in node_usage.items():
        node_spans.set_gen_ai_usage(node_id, row)
    if node_usage:
        tracked_total = sum(int(u.get("total_tokens") or 0) for u in node_usage.values())
        if tracked_total:
            total_tokens = tracked_total

        def _apply_usage(session: Session, run: models.WorkflowRun) -> None:
            for node_id, usage in node_usage.items():
                nr = (
                    session.query(models.NodeResult)
                    .filter(
                        models.NodeResult.run_id == run.id,
                        models.NodeResult.node_id == node_id,
                    )
                    .first()
                )
                if nr:
                    nr.token_usage = usage
            # Trace primitives for the waterfall view.
            for call in token_tracker.calls if token_tracker else []:
                session.add(
                    models.LlmCall(
                        run_id=run.id,
                        node_id=_resolve_node_id(call.get("agent"), metadata, author_lookup),
                        model=call.get("model"),
                        prompt_text=call.get("prompt_text"),
                        completion_text=call.get("completion_text"),
                        prompt_tokens=call.get("prompt_tokens"),
                        completion_tokens=call.get("completion_tokens"),
                        thinking_tokens=call.get("thinking_tokens"),
                        total_tokens=call.get("total_tokens"),
                        cost_usd=call.get("cost_usd"),
                        latency_ms=call.get("latency_ms"),
                    )
                )

        await _with_run_session(run_id, _apply_usage)

    # Trust-layer nested trace: persist llm/tool child spans keyed to their node
    # (via the agent→node map). Node parent spans + geometry are synthesized at
    # read time from NodeResults (timeline pattern) in GET /runs/{id}/trace.
    trace_children: list[dict[str, Any]] = []
    for call in (token_tracker.calls if token_tracker else []):
        nid = _resolve_node_id(call.get("agent"), metadata, author_lookup)
        if not nid:
            continue
        trace_children.append(
            {
                "kind": "llm_call",
                "node_id": nid,
                "name": call.get("model") or "llm call",
                "status": "completed",
                "duration_ms": call.get("latency_ms"),
                "started_wall": call.get("started_wall"),
                "attributes": {
                    "prompt": call.get("prompt_text"),
                    "completion": call.get("completion_text"),
                },
                "tokens": {
                    "prompt": call.get("prompt_tokens"),
                    "completion": call.get("completion_tokens"),
                    "thinking": call.get("thinking_tokens"),
                    "total": call.get("total_tokens"),
                },
                "cost_usd": call.get("cost_usd"),
            }
        )
    for tool_call in (trace_plugin.tool_calls if trace_plugin else []):
        nid = _resolve_node_id(tool_call.get("agent"), metadata, author_lookup)
        if not nid:
            continue
        trace_children.append(
            {
                "kind": "tool_call",
                "node_id": nid,
                "name": tool_call.get("name") or "tool",
                "status": tool_call.get("status") or "completed",
                "duration_ms": tool_call.get("latency_ms"),
                "started_wall": tool_call.get("started_wall"),
                "attributes": {
                    "args": tool_call.get("args"),
                    "result": tool_call.get("result"),
                    "error": tool_call.get("error"),
                },
                "tokens": None,
                "cost_usd": None,
            }
        )

    if trace_children:
        trace_children.sort(key=lambda c: c.get("started_wall") or 0)

        def _apply_spans(session: Session, run: models.WorkflowRun) -> None:
            for child in trace_children:
                attrs = dict(child["attributes"] or {})
                if child.get("started_wall") is not None:
                    attrs["started_wall"] = child["started_wall"]
                session.add(
                    models.RunSpan(
                        run_id=run.id,
                        parent_span_id=None,
                        node_id=child["node_id"],
                        kind=child["kind"],
                        name=str(child["name"])[:255],
                        status=child["status"],
                        offset_ms=None,
                        duration_ms=child.get("duration_ms"),
                        attributes_json=attrs or None,
                        tokens_json=child.get("tokens"),
                        cost_usd=child.get("cost_usd"),
                    )
                )

        await _with_run_session(run_id, _apply_spans)

    total_cost_usd = round(
        sum(float(u.get("cost_usd") or 0) for u in node_usage.values()), 6
    ) if node_usage else None

    end_node_ids = [
        nid for nid, meta in metadata.items() if meta.get("type") == "end" and not meta.get("is_annotation")
    ]
    if end_node_ids and end_node_ids[0] in node_outputs:
        resolved_final_output = node_outputs[end_node_ids[0]]
    else:
        resolved_final_output = final_output or (list(node_outputs.values())[-1] if node_outputs else None)
    aggregates = [
        row["aggregate_score"]
        for row in eval_score_rows
        if isinstance(row.get("aggregate_score"), (int, float))
    ]
    eval_passed = apply_eval_threshold(eval_score_rows, metadata)

    # Fold workflow-level policy verdicts (from the ADK plugin) into the same
    # metrics the Trust surface reads, alongside node-level guardrail events.
    policy_events = guardrail_policy_plugin.events if guardrail_policy_plugin else []
    policy_blocked = bool(guardrail_policy_plugin and guardrail_policy_plugin.blocked)
    all_guardrail_events = guardrail_events + policy_events
    all_failed_guardrails = failed_guardrails + [
        e["node_label"] for e in policy_events if e["status"] == "failed"
    ]

    def _complete_run(session: Session, run: models.WorkflowRun) -> models.WorkflowRun:
        completed_at = datetime.now(timezone.utc)
        metrics_payload = {
            "latency_ms": int(
                (_as_utc(completed_at) - _as_utc(run.started_at)).total_seconds() * 1000
            )
            if run.started_at
            else None,
            "total_tokens": total_tokens,
            "total_cost_usd": total_cost_usd,
            "node_count": len(metadata),
            "eval_scores": eval_score_rows,
            "eval_aggregate": round(sum(aggregates) / len(aggregates), 2)
            if aggregates
            else None,
            "eval_passed": eval_passed,
            "failed_guardrails": all_failed_guardrails,
            "guardrail_events": all_guardrail_events,
            "guardrail_blocked": policy_blocked,
            "workflow_context": workflow_context.snapshot_for_metrics(),
        }
        # Worker-mode stop_run sets cancel_requested + cancelled; do not clobber it.
        if _is_cancel_requested(run):
            _merge_run_metrics(run, metrics_payload)
            if run.status != "cancelled":
                run.status = "cancelled"
            run.completed_at = run.completed_at or completed_at
            return run
        run.status = "completed"
        run.final_output = resolved_final_output
        run.completed_at = completed_at
        _merge_run_metrics(run, metrics_payload)
        return run

    completed_run = await _with_run_session(run_id, _complete_run)
    workflow = completed_run.version.workflow if completed_run and completed_run.version else None
    quality_webhook_for_run(None, completed_run, workflow)

    # Online sampling: score a fraction of production runs that carry no eval
    # nodes, without adding latency to the run itself.
    if (
        settings.online_eval_sample_rate > 0
        and not eval_score_rows
        and resolved_final_output
    ):
        import random

        if random.random() < settings.online_eval_sample_rate:
            schedule_task(_sampled_online_eval(run_id, resolved_final_output, input_text))

    clear_approval_state(run_key)

    def _load_node_results(session: Session, run: models.WorkflowRun) -> list[dict[str, Any]]:
        return [
            {
                "id": str(nr.id),
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
            for nr in session.query(models.NodeResult).filter(models.NodeResult.run_id == run.id).all()
        ]

    node_results = await _with_run_session(run_id, _load_node_results, commit=False)

    _put_run_event(event_queue,
        {
            "type": "run_completed",
            "run_id": str(run_id),
            "final_output": resolved_final_output,
            "metrics": completed_run.metrics_json if completed_run else {},
            "node_results": node_results or [],
        }
    )


async def _sampled_online_eval(run_id: uuid.UUID, output: str, request_text: str) -> None:
    """Asynchronously score a sampled run and attach results to its metrics."""
    from app.services.eval_runner import evaluate_content_async

    try:
        scores = await evaluate_content_async(output, request_context=request_text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Online eval failed", extra={"run_id": str(run_id), "error": str(exc)})
        return
    scores.pop("_token_usage", None)

    def _attach(session: Session, run: models.WorkflowRun) -> None:
        metrics = dict(run.metrics_json or {})
        metrics["online_eval"] = scores
        if metrics.get("eval_aggregate") is None and scores.get("aggregate_score") is not None:
            metrics["eval_aggregate"] = scores["aggregate_score"]
        run.metrics_json = metrics

    await _with_run_session(run_id, _attach)


async def execute_run(run_id: uuid.UUID) -> None:
    _ensure_api_key()
    run_key = str(run_id)
    event_queue = _run_events.setdefault(run_key, _RunEventBroker())
    workflow = None
    workflow_id: str | None = None
    workflow_name: str | None = None
    webhook_url: str | None = None
    # Populated by the run body as nodes execute; read by the broad exception
    # handler below to attribute a failure to the node that blew up.
    error_context: dict[str, Any] = {}

    try:
        setup_db = _run_session()
        try:
            run = _load_run(setup_db, run_id)
            if not run:
                return
            if not run.version:
                run.status = "failed"
                run.final_output = "Workflow version not found"
                run.completed_at = datetime.now(timezone.utc)
                setup_db.commit()
                return
            if run.status in ("completed", "failed", "cancelled"):
                return

            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            setup_db.commit()

            workflow = run.version.workflow if run.version else None
            workflow_id = str(workflow.id) if workflow else None
            workflow_name = workflow.name if workflow else None
            webhook_url = workflow.webhook_url if workflow else None
            graph_json = run.version.graph_json
            input_text = run.input_text or ""
            workflow_uuid = workflow.id if workflow else None
            workflow_user_id = workflow.user_id if workflow else None
            # Persisted pin/run-from-here overrides — the worker process never
            # populates the in-memory registry, so read them off the run row.
            persisted_overrides = run.authoring_overrides_json or None
        finally:
            setup_db.close()

        with workflow_run_span(run_key, workflow_id, workflow_name):
            trace_id = get_trace_id()
            if trace_id:

                def _set_trace(session: Session, db_run: models.WorkflowRun) -> None:
                    metrics = dict(db_run.metrics_json or {})
                    metrics["trace_id"] = trace_id
                    db_run.metrics_json = metrics

                await _with_run_session(run_id, _set_trace)

            log_context(
                logger,
                logging.INFO,
                "Run started",
                run_id=run_key,
                workflow_id=workflow_id,
                event="run_started",
                trace_id=trace_id,
            )

            run_started_event: dict[str, Any] = {"type": "run_started", "run_id": run_key}
            if trace_id:
                run_started_event["trace_id"] = trace_id
            _put_run_event(event_queue,run_started_event)

            notify_run = await _with_run_session(run_id, lambda _session, db_run: db_run, commit=False)
            if notify_run:
                await _notify_observability(notify_run, "run_started", trace_id=trace_id)

            overrides = _authoring_overrides.pop(run_key, None)
            if overrides is None and persisted_overrides:
                # Worker mode (or any process that didn't create the run): the
                # in-memory registry is empty, so fall back to the run row.
                overrides = {
                    "pinned_outputs": persisted_overrides.get("pinned_outputs") or {},
                    "start_node_id": persisted_overrides.get("start_node_id"),
                }
            await _run_workflow(
                run_id,
                graph_json,
                event_queue,
                input_text=input_text,
                workflow_user_id=workflow_user_id,
                workflow_id=workflow_uuid,
                error_context=error_context,
                authoring_overrides=overrides,
            )

        run = await _with_run_session(run_id, lambda _session, db_run: db_run, commit=False)
        if run and webhook_url:
            schedule_task(
                dispatch_webhook(
                    webhook_url,
                    {
                        "event": "run_completed" if run.status == "completed" else f"run_{run.status}",
                        "run_id": run_key,
                        "workflow_id": workflow_id,
                        "status": run.status,
                        "final_output": run.final_output,
                        "metrics": run.metrics_json,
                    },
                )
            )
        finished_trace_id = None
        if run and run.metrics_json:
            finished_trace_id = run.metrics_json.get("trace_id")
        log_context(
            logger,
            logging.INFO,
            f"Run finished: {run.status if run else 'unknown'}",
            run_id=run_key,
            workflow_id=workflow_id,
            event="run_finished",
            trace_id=finished_trace_id or get_trace_id(),
        )

    except asyncio.CancelledError:

        def _cancel(session: Session, run: models.WorkflowRun) -> None:
            run.status = "cancelled"
            run.completed_at = datetime.now(timezone.utc)

        await _with_run_session(run_id, _cancel)
        _put_run_event(event_queue,{"type": "run_cancelled", "run_id": run_key})
        raise

    except asyncio.TimeoutError:

        def _timeout(session: Session, run: models.WorkflowRun) -> None:
            run.status = "failed"
            run.final_output = f"Workflow timed out after {settings.run_timeout_seconds}s"
            run.completed_at = datetime.now(timezone.utc)

        await _with_run_session(run_id, _timeout)
        _put_run_event(event_queue,
            {
                "type": "run_failed",
                "run_id": run_key,
                "error": f"Workflow timed out after {settings.run_timeout_seconds}s",
            }
        )

    except GuardrailBlockedError as exc:
        _put_run_event(event_queue,
            {
                "type": "run_failed",
                "run_id": run_key,
                "error": str(exc),
                "guardrail_node_id": exc.node_id,
            }
        )

    except EvalThresholdBlockedError as exc:
        _put_run_event(event_queue,
            {
                "type": "run_failed",
                "run_id": run_key,
                "error": str(exc),
                "eval_node_id": exc.node_id,
            }
        )

    except HumanApprovalDenied as exc:
        clear_approval_state(run_key)

        def _deny(session: Session, run: models.WorkflowRun) -> None:
            metrics_payload = {
                "approval_denied": True,
                "node_id": exc.node_id,
                "comment": exc.comment,
            }
            if _is_cancel_requested(run):
                _merge_run_metrics(run, metrics_payload)
                return
            run.status = "failed"
            run.final_output = f"Approval denied at node {exc.node_id}: {exc.comment or 'rejected'}"
            run.completed_at = datetime.now(timezone.utc)
            _merge_run_metrics(run, metrics_payload)

        await _with_run_session(run_id, _deny)
        _put_run_event(event_queue,
            {
                "type": "run_failed",
                "run_id": run_key,
                "error": str(exc),
                "approval_node_id": exc.node_id,
            }
        )

    except Exception as exc:
        failed_node_id = error_context.get("last_node_id")
        failed_node_type = error_context.get("last_node_type")
        logger.exception(
            "Run failed with unexpected error",
            extra={
                "run_id": run_key,
                "failed_node_id": failed_node_id,
                "failed_node_type": failed_node_type,
            },
        )

        def _fail(session: Session, run: models.WorkflowRun) -> None:
            if _is_cancel_requested(run):
                return
            run.status = "failed"
            run.final_output = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            if failed_node_id:
                _merge_run_metrics(
                    run,
                    {
                        "failed_node_id": failed_node_id,
                        "failed_node_type": failed_node_type,
                        "failed_node_label": error_context.get("last_node_label"),
                    },
                )

        await _with_run_session(run_id, _fail)
        failed_event: dict[str, Any] = {"type": "run_failed", "run_id": run_key, "error": str(exc)}
        if failed_node_id:
            failed_event["failed_node_id"] = failed_node_id
            failed_event["failed_node_type"] = failed_node_type
        _put_run_event(event_queue, failed_event)

    finally:
        run = await _with_run_session(run_id, lambda _session, db_run: db_run, commit=False)
        if run:
            workflow = run.version.workflow if run.version else None
            if workflow:

                def _rollup(session: Session, db_run: models.WorkflowRun) -> None:
                    record_run_rollup(
                        session,
                        user_id=workflow.user_id,
                        workflow_id=workflow.id,
                        status=db_run.status,
                        metrics=db_run.metrics_json,
                    )

                try:
                    await _with_run_session(run_id, _rollup)
                except Exception:
                    logger.exception("Failed to record observability rollup", extra={"run_id": run_key})
            event_type = {
                "completed": "run_completed",
                "failed": "run_failed",
                "cancelled": "run_cancelled",
            }.get(run.status, "run_updated")
            await _notify_observability(run, event_type)
            if run.status == "completed" and workflow:
                from app.services.regression_alerts import maybe_emit_eval_regression

                await maybe_emit_eval_regression(run, workflow)
        _put_run_event(event_queue,{"type": "stream_end"})
        cleanup_task = asyncio.create_task(_schedule_run_event_cleanup(run_key))
        _cleanup_tasks.add(cleanup_task)
        cleanup_task.add_done_callback(_cleanup_tasks.discard)
        _active_tasks.pop(run_key, None)
        _authoring_overrides.pop(run_key, None)


def schedule_run(run_id: uuid.UUID) -> None:
    run_key = str(run_id)
    existing = _active_tasks.get(run_key)
    if existing is not None and not existing.done():
        return
    _run_events.setdefault(run_key, _RunEventBroker())
    task = asyncio.create_task(execute_run(run_id))
    _active_tasks[run_key] = task


async def shutdown_active_runs() -> None:
    tasks = list(_active_tasks.items())
    for run_id, task in tasks:
        if not task.done():
            task.cancel()
    for _run_id, task in tasks:
        if not task.done():
            try:
                await task
            except asyncio.CancelledError:
                pass
    _active_tasks.clear()


def active_run_count() -> int:
    return len(_active_tasks)


def active_run_ids() -> set[str]:
    """Run ids that currently have a live in-process asyncio task."""
    return set(_active_tasks.keys())


async def cancel_run(run_id: str) -> bool:
    task = _active_tasks.get(run_id)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        return True
    return False


async def stream_run_events(run_id: str) -> AsyncGenerator[dict[str, Any], None]:
    broker = _run_events.setdefault(run_id, _RunEventBroker())
    # If the run already terminated (stream_end broadcast) there is nothing more
    # to receive; emit stream_end so the client closes cleanly instead of
    # blocking on heartbeats forever.
    if broker.terminated:
        yield {"type": "stream_end"}
        return
    event_queue = broker.subscribe()
    try:
        while True:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=30)
            except asyncio.TimeoutError:
                yield {"type": "heartbeat"}
                continue
            yield event
            if event.get("type") == "stream_end":
                break
    finally:
        broker.unsubscribe(event_queue)
        if not broker.subscribers:
            active = _active_tasks.get(run_id)
            if active is None or active.done():
                _run_events.pop(run_id, None)