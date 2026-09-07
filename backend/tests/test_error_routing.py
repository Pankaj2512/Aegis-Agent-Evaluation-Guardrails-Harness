"""Tests for per-node error-branch routing (n8n-style).

A node that fails but carries an outgoing edge tagged ``data.route == "error"``
routes down that edge instead of failing the run. Success takes the normal
edge(s); the error edge is not taken. Nodes without an error edge keep the old
behavior (the run fails). Covers the wrapper, end-to-end routing through the ADK
runner, and the graph-validation rejections.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.services.compiler import compile_workflow
from app.services.context_wrapper import ERROR_ROUTE, SUCCESS_ROUTE, wrap_with_context
from app.services.graph_validation import GraphValidationError, validate_workflow_graph
from tests.conftest import valid_graph


class _FakeCtx:
    """Minimal stand-in for the ADK Context the wrapper writes ctx.route on."""

    def __init__(self) -> None:
        self.route = None


# --------------------------------------------------------------------------- #
# Wrapper unit tests
# --------------------------------------------------------------------------- #

def test_wrapper_routes_error_on_failure():
    ctx_ref: dict = {"input": {"text": "x"}, "steps": {}, "last_output": "x"}

    def boom(_):
        raise ValueError("kaboom")

    wrapped = wrap_with_context("n1", boom, ctx_ref, node_type="transform", error_branch=True)
    fake = _FakeCtx()
    out = asyncio.run(wrapped(fake, "in"))

    assert fake.route == ERROR_ROUTE
    payload = json.loads(out)
    assert payload == {"error": "kaboom", "node_id": "n1", "node_type": "transform"}
    assert ctx_ref["_error_routed"]["n1"]["error"] == "kaboom"


def test_wrapper_success_sets_success_route():
    ctx_ref: dict = {"input": {"text": "x"}, "steps": {}, "last_output": "x"}

    def ok(value):
        return f"out:{value}"

    wrapped = wrap_with_context("n1", ok, ctx_ref, node_type="transform", error_branch=True)
    fake = _FakeCtx()
    out = asyncio.run(wrapped(fake, "in"))

    assert out == "out:in"
    assert fake.route == SUCCESS_ROUTE
    assert "_error_routed" not in ctx_ref


def test_wrapper_reraises_without_error_branch():
    ctx_ref: dict = {"input": {"text": "x"}, "steps": {}, "last_output": "x"}

    def boom(_):
        raise ValueError("kaboom")

    wrapped = wrap_with_context("n1", boom, ctx_ref, node_type="transform", error_branch=False)
    with pytest.raises(ValueError):
        asyncio.run(wrapped(_FakeCtx(), "in"))


# --------------------------------------------------------------------------- #
# End-to-end routing through the ADK runner (no LLM calls)
# --------------------------------------------------------------------------- #

def _error_graph(with_error_edge: bool = True) -> dict:
    """input_schema with a required field fails deterministically when the field
    is absent — a non-LLM, no-network way to force a node failure."""
    nodes = [
        {"id": "trg", "data": {"nodeType": "trigger", "triggerType": "manual"}},
        {"id": "fail", "data": {"nodeType": "input_schema",
                                "inputFields": [{"key": "email", "required": True}]}},
        {"id": "ok", "data": {"nodeType": "transform", "template": "OK:{{last_output}}"}},
        {"id": "end", "data": {"nodeType": "end"}},
    ]
    edges = [
        {"id": "e1", "source": "trg", "target": "fail"},
        {"id": "e2", "source": "fail", "target": "ok"},
        {"id": "e4", "source": "ok", "target": "end"},
    ]
    if with_error_edge:
        nodes.append({"id": "err", "data": {"nodeType": "transform", "template": "ERR:{{last_output}}"}})
        edges.append({"id": "e3", "source": "fail", "target": "err", "data": {"route": "error"}})
        edges.append({"id": "e5", "source": "err", "target": "end"})
    return {"nodes": nodes, "edges": edges}


def _run(graph: dict, input_text: str) -> dict:
    ctx: dict = {"input": {"text": input_text}, "steps": {}, "last_output": input_text, "memory": {}}
    workflow, _meta, _lookup = compile_workflow(graph, context_ref=ctx)
    runner = Runner(
        app_name="test",
        node=workflow,
        session_service=InMemorySessionService(),
        auto_create_session=True,
    )

    async def _drive() -> None:
        async for _event in runner.run_async(
            user_id="test-user",
            session_id=str(uuid.uuid4()),
            new_message=types.Content(parts=[types.Part(text=input_text)]),
        ):
            pass

    asyncio.run(_drive())
    return ctx


def test_error_branch_taken_on_failure():
    ctx = _run(_error_graph(True), '{"name": "no-email"}')
    steps = ctx["steps"]
    assert "err" in steps, f"error branch did not run; steps={list(steps)}"
    assert "ok" not in steps, "success branch must not run on failure"
    assert "end" in steps, "run should continue to end down the error branch"
    # telemetry stays honest — the failure was recorded
    assert ctx["_error_routed"]["fail"]["node_type"] == "input_schema"
    # the error branch received the JSON error payload as its input
    assert "email" in steps["err"]["output"]


def test_error_branch_not_taken_on_success():
    ctx = _run(_error_graph(True), '{"email": "a@b.com"}')
    steps = ctx["steps"]
    assert "ok" in steps, "success branch should run"
    assert "err" not in steps, "error branch must not run on success"
    assert "_error_routed" not in ctx


def test_run_fails_without_error_edge():
    # Zero behavior change for graphs with no error edge: the failure propagates.
    with pytest.raises(ValueError):
        _run(_error_graph(False), '{"name": "no-email"}')


# --------------------------------------------------------------------------- #
# Validation rejections
# --------------------------------------------------------------------------- #

def test_validation_allows_single_error_edge_from_handler_node():
    graph = valid_graph(
        [
            {"id": "t", "data": {"nodeType": "transform", "template": "{{input}}"}},
            {"id": "ok", "data": {"nodeType": "transform", "template": "OK"}},
            {"id": "err", "data": {"nodeType": "transform", "template": "ERR"}},
        ],
        [
            {"id": "e-tok", "source": "t", "target": "ok"},
            {"id": "e-terr", "source": "t", "target": "err", "data": {"route": "error"}},
            {"id": "e-oke", "source": "ok", "target": "err"},
        ],
        entry_id="t",
        exit_id="err",
    )
    summary = validate_workflow_graph(graph)
    assert summary["node_count"] == 5  # trigger, t, ok, err, end


def test_validation_rejects_multiple_error_edges():
    graph = valid_graph(
        [
            {"id": "t", "data": {"nodeType": "transform", "template": "{{input}}"}},
            {"id": "a", "data": {"nodeType": "transform", "template": "A"}},
            {"id": "b", "data": {"nodeType": "transform", "template": "B"}},
        ],
        [
            {"id": "e-ta", "source": "t", "target": "a", "data": {"route": "error"}},
            {"id": "e-tb", "source": "t", "target": "b", "data": {"route": "error"}},
            {"id": "e-ab", "source": "a", "target": "b"},
        ],
        entry_id="t",
        exit_id="b",
    )
    with pytest.raises(GraphValidationError, match="error branch is allowed"):
        validate_workflow_graph(graph)


def test_validation_rejects_error_edge_from_llm_node():
    graph = valid_graph(
        [
            {"id": "ag", "data": {"nodeType": "agent", "instruction": "hi"}},
            {"id": "h", "data": {"nodeType": "transform", "template": "H"}},
        ],
        [
            {"id": "e-agh", "source": "ag", "target": "h", "data": {"route": "error"}},
        ],
        entry_id="ag",
        exit_id="h",
    )
    with pytest.raises(GraphValidationError, match="does not support an error branch"):
        validate_workflow_graph(graph)


def test_validation_rejects_error_edge_from_end_is_moot_but_trigger_covered():
    # An error edge from the trigger is rejected (structural node).
    graph = {
        "nodes": [
            {"id": "trigger", "data": {"nodeType": "trigger", "triggerType": "manual"}},
            {"id": "h", "data": {"nodeType": "transform", "template": "H"}},
            {"id": "end", "data": {"nodeType": "end"}},
        ],
        "edges": [
            {"id": "e1", "source": "trigger", "target": "h", "data": {"route": "error"}},
            {"id": "e2", "source": "h", "target": "end"},
        ],
    }
    with pytest.raises(GraphValidationError, match="does not support an error branch"):
        validate_workflow_graph(graph)
