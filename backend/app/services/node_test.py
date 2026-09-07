"""Ephemeral single-node testing and expression preview.

Two authoring aids that execute against the workflow's *current* (latest-version)
graph without ever persisting a run:

* :func:`run_node_test` — execute exactly one node with a synthetic input and
  optional simulated upstream outputs, returning its output/verdict. No
  WorkflowRun/NodeResult rows, no observability, no SSE. Handler-backed nodes run
  through the same ``_make_*_fn`` factories the compiler uses (imported via
  :func:`app.services.compiler._build_adk_node`); LLM-family nodes do one direct
  Gemini call reproducing the compiler's instruction assembly.
* :func:`preview_expression` — render a ``{{expression}}`` against a real run's
  context (or the most recent run, or a sample input) so the canvas can show a
  live preview.

Ownership queries are local copies of the patterns in ``app/api/workflows.py``
(that router is intentionally not edited), mirroring how ``app/api/assist.py``
keeps a local ``_get_user_run``.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import time
from collections import defaultdict
from threading import Lock
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.db import models
from app.services.eval import EvalScores, build_eval_instruction
from app.services.eval_deterministic import run_deterministic_evaluation
from app.services.expressions import render_template
from app.services.guardrail import validate_guardrail_content
from app.services.routing_models import ClassifierDecision, RouterDecision
from app.services.workflow_context import WorkflowContext

# ---------------------------------------------------------------------------
# Node type policy
# ---------------------------------------------------------------------------

# LLM-family nodes: one direct Gemini call reproducing the node's instruction.
LLM_FAMILY_TYPES = {"agent", "summarizer", "translator", "extractor", "router", "classifier"}

# Types that cannot be meaningfully executed in isolation. Each maps to an
# honest reason surfaced to the UI.
UNSUPPORTED_NODE_TYPES: dict[str, str] = {
    "trigger": "Trigger only marks the workflow entry; it has nothing to execute standalone.",
    "end": "End only marks the workflow terminal; it passes input through with nothing to test.",
    "note": "Sticky notes are annotations and are never executed.",
    "group": "Groups are visual containers with no execution behavior.",
    "join": "Join fans in multiple parallel branches; it needs a full run to have inputs to merge.",
    "human_approval": "Human Approval pauses for an out-of-band approval that only exists during a live run.",
    "sub_workflow": "Sub-workflow executes another workflow end-to-end; run the child workflow directly instead.",
    "delay": "Delay only waits then passes input through unchanged; there is nothing to preview.",
    "input_schema": "Input Schema validates workflow-level inputs and only has meaning as a run's entry.",
}

_NO_KEY_ERROR = "GOOGLE_API_KEY is not configured. Add it to .env to test LLM nodes."

# Hard wall-clock cap for a single node test (contract: ~30s).
NODE_TEST_TIMEOUT_SECONDS = 30

MAX_INPUT_BYTES = 32 * 1024
MAX_EXPRESSION_BYTES = 8 * 1024
MAX_RENDERED_BYTES = 16 * 1024
_TRUNCATION_SUFFIX = "… [truncated]"


class NodeNotFoundError(Exception):
    """Requested node_id is absent from the workflow's current graph."""


# ---------------------------------------------------------------------------
# Ownership helpers (local copies — workflows.py is not edited)
# ---------------------------------------------------------------------------


def get_user_workflow(db: Session, workflow_id: UUID, user_id: UUID) -> models.Workflow:
    workflow = (
        db.query(models.Workflow)
        .filter(models.Workflow.id == workflow_id, models.Workflow.user_id == user_id)
        .first()
    )
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


def latest_graph(db: Session, workflow_id: UUID) -> dict:
    """The graph the canvas edits: the latest version's graph_json."""
    version = (
        db.query(models.WorkflowVersion)
        .filter(models.WorkflowVersion.workflow_id == workflow_id)
        .order_by(models.WorkflowVersion.version_number.desc())
        .first()
    )
    if not version:
        raise HTTPException(status_code=404, detail="Workflow has no versions")
    return version.graph_json or {"nodes": [], "edges": []}


# ---------------------------------------------------------------------------
# Rate limiting (per-user, in-memory, always on — mirrors assist.py)
# ---------------------------------------------------------------------------

_rate_lock = Lock()
_rate_buckets: dict[str, list[float]] = defaultdict(list)


def check_node_test_rate_limit(user_id: str) -> None:
    limit = max(1, int(settings.node_test_per_minute))
    window_seconds = 60.0
    now = time.monotonic()
    key = f"{user_id}:node_test"
    with _rate_lock:
        recent = [ts for ts in _rate_buckets[key] if now - ts < window_seconds]
        if len(recent) >= limit:
            _rate_buckets[key] = recent
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded ({limit} requests per minute)",
            )
        recent.append(now)
        _rate_buckets[key] = recent


# ---------------------------------------------------------------------------
# Context assembly
# ---------------------------------------------------------------------------


def _node_data(node: dict) -> dict:
    return node.get("data", {}) or {}


def _normalize_steps(raw: Any) -> dict[str, Any]:
    """Coerce simulated upstream outputs into the executor's step shape.

    The wire contract is a flat ``{node_id: "output string"}``; the expression
    engine (and every real run) stores steps as ``{node_id: {"output": ...}}``
    so ``{{steps.x.output}}`` resolves. We normalize flat strings into that
    shape while passing through any already-structured entries.
    """
    steps: dict[str, Any] = {}
    if isinstance(raw, dict):
        for node_id, value in raw.items():
            if isinstance(value, dict):
                steps[str(node_id)] = value
            else:
                steps[str(node_id)] = {
                    "output": "" if value is None else str(value),
                    "label": str(node_id),
                    "type": None,
                }
    return steps


def _build_test_context(
    input_text: str,
    extra_context: dict | None,
    *,
    workflow_id: UUID | None = None,
    user_id: UUID | None = None,
) -> dict[str, Any]:
    # Reuse the real run's context construction so input.text / input.<field>
    # resolve identically to a live run.
    context = WorkflowContext.from_input(input_text).to_dict()
    context["last_output"] = input_text
    steps_source = (extra_context or {}).get("steps") if isinstance(extra_context, dict) else None
    context["steps"] = _normalize_steps(steps_source)
    context.setdefault("memory", {})
    # Ephemeral run plumbing: identify the workflow/user so kb_retrieve(workflow),
    # integrations, and credential lookups resolve real reads. No _run_id / _emit
    # are set (there is no run and no stream); persistent memory writes only queue
    # in-context and are never flushed, so nothing is persisted.
    if workflow_id is not None:
        context["_workflow_id"] = str(workflow_id)
        context["_user_id"] = str(user_id) if user_id else None
    return context


# ---------------------------------------------------------------------------
# Node execution
# ---------------------------------------------------------------------------


def _gemini_text(instruction: str, node_input: str, *, response_schema: type | None = None) -> str:
    """One direct Gemini call, mirroring compiler.py's agent prompt assembly."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.google_api_key)
    config_kwargs: dict[str, Any] = {"system_instruction": instruction}
    if response_schema is not None:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = response_schema
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=str(node_input),
        config=types.GenerateContentConfig(**config_kwargs),
    )
    return response.text or ""


def _format_result(result: Any) -> str:
    if result is None:
        return ""
    if isinstance(result, (RouterDecision, ClassifierDecision)):
        return json.dumps(
            {"route": str(result.route), "reasoning": result.reasoning},
            ensure_ascii=False,
        )
    return str(result)


async def _execute_node(
    node: dict,
    node_type: str,
    node_input: str,
    context_ref: dict[str, Any],
) -> tuple[str, str | None, str | None]:
    """Return (status, output, error). Raises only for unknown node types."""
    data = _node_data(node)

    # Guardrail: surface the verdict directly (never raise on a block here).
    if node_type == "guardrail":
        rules = data.get("rules", {}) or {}
        result = await asyncio.to_thread(validate_guardrail_content, str(node_input), rules)
        output = json.dumps({"passed": result.passed, "message": result.message}, ensure_ascii=False)
        return "completed", output, None

    # Evaluation: LLM judge (direct call) or deterministic scorer (no LLM).
    if node_type == "evaluation":
        eval_type = (data.get("evalType") or "llm").lower()
        if eval_type == "llm":
            if not settings.google_api_key:
                return "failed", None, _NO_KEY_ERROR
            instruction = data.get("evalInstruction") or build_eval_instruction(
                data.get("evalPreset"), data.get("criteria")
            )
            text = await asyncio.to_thread(
                _gemini_text, instruction, node_input, response_schema=EvalScores
            )
            return "completed", text, None
        meta = {
            "eval_expected": data.get("evalExpected"),
            "eval_pattern": data.get("evalPattern"),
            "eval_tolerance": data.get("evalTolerance"),
            "eval_baseline": data.get("evalBaseline"),
            "eval_similarity_threshold": data.get("evalSimilarityThreshold"),
        }
        scores = await asyncio.to_thread(
            run_deterministic_evaluation, eval_type, str(node_input), meta
        )
        return "completed", json.dumps(scores, ensure_ascii=False), None

    # Everything else is built exactly as the compiler would build it.
    from app.services.compiler import _build_adk_node
    from google.adk import Agent

    built = _build_adk_node(node, None, context_ref)

    # Native ADK Agent → one direct Gemini call using its assembled instruction.
    if isinstance(built, Agent):
        if not settings.google_api_key:
            return "failed", None, _NO_KEY_ERROR
        instruction = getattr(built, "instruction", "") or ""
        out_schema = getattr(built, "output_schema", None)
        schema = out_schema if isinstance(out_schema, type) and out_schema is not str else None
        text = await asyncio.to_thread(_gemini_text, instruction, node_input, response_schema=schema)
        return "completed", text, None

    # LLM-decision callables (router/classifier) and expression-agents call
    # Gemini internally; short-circuit with a clean error when there is no key.
    if node_type in LLM_FAMILY_TYPES and not settings.google_api_key:
        return "failed", None, _NO_KEY_ERROR

    if callable(built):
        if inspect.iscoroutinefunction(built):
            result = await built(node_input)
        else:
            result = await asyncio.to_thread(built, node_input)
        return "completed", _format_result(result), None

    return "unsupported", None, "Node type cannot be executed standalone."


async def run_node_test(
    graph_json: dict,
    workflow_id: UUID,
    user_id: UUID,
    node_id: str,
    input_text: str,
    extra_context: dict | None,
    node_data: dict | None = None,
) -> dict[str, Any]:
    """Execute a single node ephemerally. Raises NodeNotFoundError for 404.

    When ``node_data`` is provided (the node's current on-canvas data), it is
    preferred over the persisted graph node so unsaved inspector edits are what
    gets tested; an unsaved node absent from the graph is synthesized from it
    rather than 404ing.
    """
    node = next(
        (n for n in (graph_json.get("nodes") or []) if n.get("id") == node_id),
        None,
    )
    if node_data is not None:
        # Prefer the live canvas data. Build (or overlay onto) the graph node so
        # the compiler sees exactly the config the user is editing.
        base = dict(node or {"id": node_id})
        base["data"] = node_data
        node = base
    if node is None:
        raise NodeNotFoundError(node_id)

    node_type = _node_data(node).get("nodeType", "agent")

    if node_type in UNSUPPORTED_NODE_TYPES:
        return {
            "node_id": node_id,
            "status": "unsupported",
            "output": None,
            "error": UNSUPPORTED_NODE_TYPES[node_type],
            "latency_ms": 0,
        }

    context_ref = _build_test_context(
        input_text, extra_context, workflow_id=workflow_id, user_id=user_id
    )

    start = time.perf_counter()
    try:
        status_, output, error = await asyncio.wait_for(
            _execute_node(node, node_type, input_text, context_ref),
            timeout=NODE_TEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        status_, output, error = (
            "failed",
            None,
            f"Node execution timed out after {NODE_TEST_TIMEOUT_SECONDS}s.",
        )
    except ValueError as exc:
        # Handlers (HTTP, calculator, …) also raise ValueError for bad runtime
        # input — those are failures, not "unsupported node type". Only treat
        # compiler construction errors as unsupported.
        msg = str(exc)
        lower = msg.lower()
        if (
            "unsupported node type" in lower
            or "annotation nodes are not compiled" in lower
            or "cannot convert" in lower
        ):
            status_, output, error = "unsupported", None, msg
        else:
            status_, output, error = "failed", None, msg
    except Exception as exc:  # noqa: BLE001 — any handler/LLM failure is data, not a 500
        status_, output, error = "failed", None, str(exc)
    latency_ms = int((time.perf_counter() - start) * 1000)

    return {
        "node_id": node_id,
        "status": status_,
        "output": output,
        "error": error,
        "latency_ms": latency_ms,
    }


# ---------------------------------------------------------------------------
# Expression preview
# ---------------------------------------------------------------------------


def _load_run_for_workflow(
    db: Session, run_id: UUID, workflow_id: UUID, user_id: UUID
) -> models.WorkflowRun | None:
    return (
        db.query(models.WorkflowRun)
        .options(joinedload(models.WorkflowRun.node_results))
        .join(models.WorkflowVersion)
        .join(models.Workflow)
        .filter(
            models.WorkflowRun.id == run_id,
            models.WorkflowVersion.workflow_id == workflow_id,
            models.Workflow.user_id == user_id,
        )
        .first()
    )


def _latest_run_for_workflow(db: Session, workflow_id: UUID) -> models.WorkflowRun | None:
    return (
        db.query(models.WorkflowRun)
        .options(joinedload(models.WorkflowRun.node_results))
        .join(models.WorkflowVersion)
        .filter(models.WorkflowVersion.workflow_id == workflow_id)
        .order_by(models.WorkflowRun.created_at.desc())
        .first()
    )


def _steps_from_run(run: models.WorkflowRun) -> dict[str, Any]:
    steps: dict[str, Any] = {}
    for nr in run.node_results or []:
        if nr.output is not None:
            steps[nr.node_id] = {
                "output": nr.output,
                "label": nr.node_label,
                "type": nr.node_type,
            }
    return steps


def _last_node_output(run: models.WorkflowRun) -> str | None:
    latest: models.NodeResult | None = None
    for nr in run.node_results or []:
        if nr.output is None:
            continue
        if latest is None or (nr.created_at and latest.created_at and nr.created_at >= latest.created_at):
            latest = nr
    return latest.output if latest is not None else None


def _cap_rendered(rendered: str) -> str:
    encoded = rendered.encode("utf-8")
    if len(encoded) <= MAX_RENDERED_BYTES:
        return rendered
    budget = MAX_RENDERED_BYTES - len(_TRUNCATION_SUFFIX.encode("utf-8"))
    truncated = encoded[: max(0, budget)].decode("utf-8", errors="ignore")
    return truncated + _TRUNCATION_SUFFIX


def preview_expression(
    db: Session,
    workflow_id: UUID,
    user_id: UUID,
    expression: str,
    run_id: str | None,
    sample_input: str | None,
) -> dict[str, Any]:
    """Render an expression against a run's context, or a sample-input fallback."""
    run: models.WorkflowRun | None = None

    if run_id:
        try:
            parsed_run_id = UUID(str(run_id))
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=404, detail="Run not found for this workflow") from exc
        run = _load_run_for_workflow(db, parsed_run_id, workflow_id, user_id)
        if run is None:
            raise HTTPException(status_code=404, detail="Run not found for this workflow")
    else:
        run = _latest_run_for_workflow(db, workflow_id)

    if run is not None:
        input_text = run.input_text or ""
        context = WorkflowContext.from_input(input_text).to_dict()
        context["steps"] = _steps_from_run(run)
        last_output = run.final_output
        if last_output is None:
            last_output = _last_node_output(run)
        if last_output is None:
            last_output = input_text
        context["last_output"] = last_output
        node_input = input_text
        used_run_id: str | None = str(run.id)
    else:
        sample = sample_input or ""
        context = {"input": {"text": sample}, "steps": {}, "last_output": sample, "memory": {}}
        node_input = sample
        input_text = sample
        last_output = sample
        used_run_id = None

    try:
        rendered: str | None = render_template(expression, context, node_input)
        error: str | None = None
    except Exception as exc:  # noqa: BLE001 — render failure is data, not a 500
        rendered, error = None, str(exc)

    if rendered is not None:
        rendered = _cap_rendered(rendered)

    step_ids = sorted((context.get("steps") or {}).keys())
    context_available = {
        "input": bool(input_text),
        "last_output": bool(last_output),
        "steps": step_ids,
    }

    return {
        "rendered": rendered,
        "error": error,
        "run_id": used_run_id,
        "context_available": context_available,
    }
