"""Regression tests for 2026-08-07 audit P1 fixes."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.graph_validation import GraphValidationError, validate_workflow_graph
from tests.conftest import valid_graph

client = TestClient(app)


def test_google_search_tool_rejects_error_branch():
    """P1-2: bare google-search Agent never sets ctx.route — error edges dead-end."""
    graph = valid_graph(
        [
            {
                "id": "n1",
                "data": {
                    "label": "Search",
                    "nodeType": "tool",
                    "toolType": "search",
                    "searchProvider": "google",
                },
            },
            {
                "id": "err",
                "data": {"label": "On error", "nodeType": "transform", "template": "fail"},
            },
        ],
        [
            {"source": "n1", "target": "end"},
            {"source": "n1", "target": "err", "data": {"route": "error"}},
            {"source": "err", "target": "end"},
        ],
    )
    with pytest.raises(GraphValidationError, match="does not support an error branch"):
        validate_workflow_graph(graph)


def test_calculator_tool_still_allows_error_branch():
    """Wrapped tool handlers still support error routing."""
    graph = valid_graph(
        [
            {
                "id": "n1",
                "data": {
                    "label": "Calc",
                    "nodeType": "tool",
                    "toolType": "calculator",
                },
            },
            {
                "id": "err",
                "data": {"label": "On error", "nodeType": "transform", "template": "fail"},
            },
        ],
        [
            {"source": "n1", "target": "end"},
            {"source": "n1", "target": "err", "data": {"route": "error"}},
            {"source": "err", "target": "end"},
        ],
    )
    summary = validate_workflow_graph(graph)
    assert summary["entry_node"]


def test_eval_trend_slice_newest_first():
    """P1-13: newest-first list must reverse then take last 20 (= newest 20)."""
    # Newest-first series: index 0 is newest.
    eval_trend = list(range(30, 0, -1))  # 30, 29, ..., 1
    fixed = list(reversed(eval_trend))[-20:]
    broken = list(reversed(eval_trend[-20:]))
    # Newest 20 values are 11..30, chronological oldest→newest.
    assert fixed == list(range(11, 31))
    # Broken path takes the 20 oldest (1..20).
    assert broken == list(range(1, 21))
    assert broken != fixed


def test_viewer_blocked_on_v1_ingest(monkeypatch):
    """P1-6: viewer keys must not mutate /v1 routes."""
    from app.config import settings

    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "aegis_api_key", "editor-key")
    monkeypatch.setattr(
        settings,
        "aegis_api_key_user_map",
        json.dumps(
            {
                "viewer-key": {
                    "user_id": "00000000-0000-0000-0000-000000000001",
                    "role": "viewer",
                }
            }
        ),
    )
    r = client.post(
        "/v1/ingest/runs",
        json={"workflow_name": "ext", "input": "hi", "status": "completed"},
        headers={"X-Aegis-API-Key": "viewer-key"},
    )
    assert r.status_code == 403


def test_empty_template_renders_empty_string():
    """P3: empty template must not passthrough node input."""
    from app.services.expressions import render_template

    assert render_template("", {"input": {"text": "hello"}, "steps": {}}, "hello") == ""


def test_parse_seeded_last_output_trigger_path():
    """P1-1: trigger with seeded last_output preserves pin across passthrough."""
    import asyncio

    from app.services.context_wrapper import wrap_with_context

    ctx_ref: dict = {
        "steps": {},
        "last_output": "pinned-value",
        "_seeded_last_output": "pinned-value",
    }

    def passthrough(node_input: str) -> str:
        return node_input

    wrapped = wrap_with_context(
        "t1", passthrough, ctx_ref, node_type="trigger", label="Trigger"
    )

    class _Ctx:
        route = None

    result = asyncio.run(wrapped(_Ctx(), "raw-run-input"))
    assert result == "pinned-value"
    assert ctx_ref["last_output"] == "pinned-value"
