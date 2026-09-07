"""Tests for MVP2 assist endpoints: edit-graph, compare, generate-schema."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.assist import (
    CompareVariantResult,
    GenEdge,
    GenNode,
    _EditGraphDraft,
    _GeneratedSchemaDraft,
)

client = TestClient(app)


def _mock_response(model_obj) -> MagicMock:
    resp = MagicMock()
    resp.text = model_obj.model_dump_json()
    return resp


def _current_graph() -> dict:
    return {
        "nodes": [
            {"id": "trigger", "data": {"label": "T", "nodeType": "trigger", "triggerType": "manual"}},
            {"id": "agent", "data": {"label": "A", "nodeType": "agent", "instruction": "help"}},
            {"id": "end", "data": {"label": "E", "nodeType": "end"}},
        ],
        "edges": [
            {"id": "e1", "source": "trigger", "target": "agent"},
            {"id": "e2", "source": "agent", "target": "end"},
        ],
    }


# ---------------------------------------------------------------------------
# edit-graph
# ---------------------------------------------------------------------------


def _edit_draft_add_guardrail() -> _EditGraphDraft:
    # Insert a guardrail between agent and end.
    return _EditGraphDraft(
        nodes=[
            GenNode(id="trigger", node_type="trigger", label="T", config_json='{"triggerType": "manual"}'),
            GenNode(id="agent", node_type="agent", label="A", config_json='{"instruction": "help"}'),
            GenNode(id="guard", node_type="guardrail", label="Guard", config_json='{"rules": {"fail_behavior": "block"}}'),
            GenNode(id="end", node_type="end", label="E", config_json=None),
        ],
        edges=[
            GenEdge(source="trigger", target="agent", route=None),
            GenEdge(source="agent", target="guard", route=None),
            GenEdge(source="guard", target="end", route=None),
        ],
        notes=["Configure the guardrail rules."],
        summary="Added an output guardrail after the agent.",
    )


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_edit_graph_returns_diff(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_response(_edit_draft_add_guardrail())

    resp = client.post(
        "/api/assist/edit-graph",
        json={"graph": _current_graph(), "instruction": "add a guardrail after the agent"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "proposed_graph" in body
    assert body["diff"]["added_node_ids"] == ["guard"]
    assert body["diff"]["removed_node_ids"] == []
    # Original edge agent->end was removed, agent->guard + guard->end added.
    added_edges = {(e["source"], e["target"]) for e in body["diff"]["added_edges"]}
    assert ("agent", "guard") in added_edges
    assert ("guard", "end") in added_edges
    removed_edges = {(e["source"], e["target"]) for e in body["diff"]["removed_edges"]}
    assert ("agent", "end") in removed_edges
    assert body["summary"]


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_edit_graph_detects_changed_node(mock_client_cls):
    draft = _EditGraphDraft(
        nodes=[
            GenNode(id="trigger", node_type="trigger", label="T", config_json='{"triggerType": "manual"}'),
            GenNode(id="agent", node_type="agent", label="A", config_json='{"instruction": "be terse"}'),
            GenNode(id="end", node_type="end", label="E", config_json=None),
        ],
        edges=[
            GenEdge(source="trigger", target="agent", route=None),
            GenEdge(source="agent", target="end", route=None),
        ],
        notes=[],
        summary="Changed the agent instruction.",
    )
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_response(draft)

    resp = client.post(
        "/api/assist/edit-graph",
        json={"graph": _current_graph(), "instruction": "make the agent terse"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["diff"]["changed_node_ids"] == ["agent"]
    assert body["diff"]["added_node_ids"] == []


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_edit_graph_retries_then_422(mock_client_cls):
    # Both attempts return an invalid graph (no end node).
    bad = _EditGraphDraft(
        nodes=[
            GenNode(id="trigger", node_type="trigger", label="T", config_json='{"triggerType": "manual"}'),
            GenNode(id="agent", node_type="agent", label="A", config_json=None),
        ],
        edges=[GenEdge(source="trigger", target="agent", route=None)],
        notes=[],
        summary="broken",
    )
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.side_effect = [_mock_response(bad), _mock_response(bad)]

    resp = client.post(
        "/api/assist/edit-graph",
        json={"graph": _current_graph(), "instruction": "break it"},
    )
    assert resp.status_code == 422
    assert mock_client.models.generate_content.call_count == 2


def test_edit_graph_no_api_key_returns_400():
    with patch("app.api.assist.settings.google_api_key", ""):
        resp = client.post(
            "/api/assist/edit-graph",
            json={"graph": _current_graph(), "instruction": "hi"},
        )
    assert resp.status_code == 400
    assert "GOOGLE_API_KEY" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# compare
# ---------------------------------------------------------------------------


def test_compare_no_api_key_degrades_to_per_variant_error():
    with patch("app.services.assist.settings.google_api_key", ""):
        resp = client.post(
            "/api/assist/compare",
            json={
                "node_type": "agent",
                "base_config": {"instruction": "answer"},
                "variants": [
                    {"label": "flash", "config_overrides": {}},
                    {"label": "pro", "config_overrides": {"model": "gemini-2.5-pro"}},
                ],
                "input_text": "hello",
            },
        )
    assert resp.status_code == 200, resp.text
    results = resp.json()["results"]
    assert len(results) == 2
    assert results[0]["label"] == "flash"
    assert results[1]["label"] == "pro"
    assert all(r["error"] and "GOOGLE_API_KEY" in r["error"] for r in results)
    assert all(r["output"] is None for r in results)


@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("app.services.assist._run_single_node_variant")
def test_compare_runs_each_variant(mock_run):
    async def _fake(node_type, config, input_text):
        return CompareVariantResult(
            label="",
            output=f"out for {config.get('instruction')}",
            latency_ms=12,
            total_tokens=34,
            cost_usd=0.001,
        )

    mock_run.side_effect = _fake

    resp = client.post(
        "/api/assist/compare",
        json={
            "node_type": "agent",
            "base_config": {"instruction": "base"},
            "variants": [
                {"label": "A", "config_overrides": {"instruction": "variant A"}},
                {"label": "B", "config_overrides": {}},
            ],
            "input_text": "hello",
        },
    )
    assert resp.status_code == 200, resp.text
    results = resp.json()["results"]
    assert [r["label"] for r in results] == ["A", "B"]
    assert results[0]["output"] == "out for variant A"
    assert results[1]["output"] == "out for base"
    assert results[0]["total_tokens"] == 34
    assert results[0]["cost_usd"] == 0.001
    assert mock_run.call_count == 2


# ---------------------------------------------------------------------------
# generate-schema
# ---------------------------------------------------------------------------


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_generate_schema_json_schema(mock_client_cls):
    draft = _GeneratedSchemaDraft(
        schema_object_json='{"type": "object", "properties": {"name": {"type": "string"}}}',
        regex=None,
        notes=["Assumed name is required."],
    )
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_response(draft)

    resp = client.post(
        "/api/assist/generate-schema",
        json={"description": "a person with a name", "kind": "json_schema"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["json_schema"]["type"] == "object"
    assert body["regex"] is None
    assert body["notes"]


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_generate_schema_regex(mock_client_cls):
    draft = _GeneratedSchemaDraft(
        schema_object_json=None,
        regex=r"^\d{3}-\d{4}$",
        notes=[],
    )
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_response(draft)

    resp = client.post(
        "/api/assist/generate-schema",
        json={"description": "phone number like 555-1234", "kind": "regex"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["regex"] == r"^\d{3}-\d{4}$"
    assert body["json_schema"] is None


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_generate_schema_bad_json_returns_422(mock_client_cls):
    draft = _GeneratedSchemaDraft(schema_object_json="not json", regex=None, notes=[])
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_response(draft)

    resp = client.post(
        "/api/assist/generate-schema",
        json={"description": "whatever"},
    )
    assert resp.status_code == 422


def test_generate_schema_no_api_key_returns_400():
    with patch("app.api.assist.settings.google_api_key", ""):
        resp = client.post(
            "/api/assist/generate-schema",
            json={"description": "hi"},
        )
    assert resp.status_code == 400
    assert "GOOGLE_API_KEY" in resp.json()["detail"]
