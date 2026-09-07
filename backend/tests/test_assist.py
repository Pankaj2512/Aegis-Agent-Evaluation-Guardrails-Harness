from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.db import models
from app.db.database import SessionLocal
from app.main import app
from app.schemas.assist import (
    ExplainRunResponse,
    GeneratedWorkflowDraft,
    GenEdge,
    GenNode,
    SuggestionsDraft,
)
from app.services import assist as assist_service
from app.services.graph_validation import validate_workflow_graph

client = TestClient(app)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _valid_draft() -> GeneratedWorkflowDraft:
    return GeneratedWorkflowDraft(
        nodes=[
            GenNode(id="trigger", node_type="trigger", label="Trigger", config_json='{"triggerType": "manual"}'),
            GenNode(id="agent", node_type="agent", label="Agent", config_json='{"instruction": "Help the user."}'),
            GenNode(id="end", node_type="end", label="End", config_json=None),
        ],
        edges=[
            GenEdge(source="trigger", target="agent", route=None),
            GenEdge(source="agent", target="end", route=None),
        ],
        notes=["Refine the agent instruction."],
    )


def _invalid_draft() -> GeneratedWorkflowDraft:
    # Missing an end node -> validation fails.
    return GeneratedWorkflowDraft(
        nodes=[
            GenNode(id="trigger", node_type="trigger", label="Trigger", config_json=None),
            GenNode(id="agent", node_type="agent", label="Agent", config_json=None),
        ],
        edges=[GenEdge(source="trigger", target="agent", route=None)],
        notes=[],
    )


def _mock_response(model_obj) -> MagicMock:
    resp = MagicMock()
    resp.text = model_obj.model_dump_json()
    return resp


def _seed_run(*, status: str = "failed", with_nodes: bool = True) -> models.WorkflowRun:
    db = SessionLocal()
    try:
        workflow = models.Workflow(id=uuid4(), user_id=DEFAULT_DEV_USER_ID, name="Assist Flow")
        db.add(workflow)
        db.flush()
        version = models.WorkflowVersion(
            id=uuid4(),
            workflow_id=workflow.id,
            version_number=1,
            graph_json={
                "nodes": [
                    {"id": "trigger", "data": {"label": "T", "nodeType": "trigger"}},
                    {"id": "agent", "data": {"label": "A", "nodeType": "agent"}},
                    {"id": "end", "data": {"label": "E", "nodeType": "end"}},
                ],
                "edges": [
                    {"id": "e-trigger-agent", "source": "trigger", "target": "agent"},
                    {"id": "e-agent-end", "source": "agent", "target": "end"},
                ],
            },
        )
        db.add(version)
        db.flush()
        run = models.WorkflowRun(
            id=uuid4(),
            workflow_version_id=version.id,
            status=status,
            input_text="do the thing",
            final_output="boom",
        )
        db.add(run)
        db.flush()
        if with_nodes:
            db.add(
                models.NodeResult(
                    id=uuid4(),
                    run_id=run.id,
                    node_id="agent",
                    node_type="agent",
                    node_label="Agent",
                    status="failed",
                    output="Traceback: exploded",
                    latency_ms=42,
                )
            )
        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()


# ---------------------------------------------------------------------------
# _assign_positions (pure unit test, no LLM)
# ---------------------------------------------------------------------------


def test_assign_positions_layers_by_depth():
    graph = {
        "nodes": [
            {"id": "trigger", "position": {"x": 0, "y": 0}, "data": {"nodeType": "trigger"}},
            {"id": "agent", "position": {"x": 0, "y": 0}, "data": {"nodeType": "agent"}},
            {"id": "end", "position": {"x": 0, "y": 0}, "data": {"nodeType": "end"}},
        ],
        "edges": [
            {"source": "trigger", "target": "agent"},
            {"source": "agent", "target": "end"},
        ],
    }
    assist_service._assign_positions(graph)
    pos = {n["id"]: n["position"] for n in graph["nodes"]}
    # Depth 0/1/2 -> distinct x columns.
    assert pos["trigger"]["x"] == 60
    assert pos["agent"]["x"] == 60 + 280
    assert pos["end"]["x"] == 60 + 560
    xs = [p["x"] for p in pos.values()]
    assert len(set(xs)) == 3


# ---------------------------------------------------------------------------
# generate-workflow
# ---------------------------------------------------------------------------


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_generate_workflow_happy_path(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_response(_valid_draft())

    resp = client.post("/api/assist/generate-workflow", json={"description": "Answer questions"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Graph is valid.
    validate_workflow_graph(body["graph"])
    assert body["notes"]
    # Distinct layered positions.
    positions = [(n["position"]["x"], n["position"]["y"]) for n in body["graph"]["nodes"]]
    assert len(set(positions)) == len(positions)
    assert mock_client.models.generate_content.call_count == 1


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_generate_workflow_retry_then_success(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.side_effect = [
        _mock_response(_invalid_draft()),
        _mock_response(_valid_draft()),
    ]

    resp = client.post("/api/assist/generate-workflow", json={"description": "retry me"})
    assert resp.status_code == 200, resp.text
    validate_workflow_graph(resp.json()["graph"])
    assert mock_client.models.generate_content.call_count == 2


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_generate_workflow_double_invalid_returns_422(mock_client_cls):
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.side_effect = [
        _mock_response(_invalid_draft()),
        _mock_response(_invalid_draft()),
    ]

    resp = client.post("/api/assist/generate-workflow", json={"description": "always broken"})
    assert resp.status_code == 422
    assert mock_client.models.generate_content.call_count == 2


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_generate_workflow_drops_unknown_node_types(mock_client_cls):
    draft = _valid_draft()
    draft.nodes.append(
        GenNode(id="bogus", node_type="not_a_real_type", label="Bogus", config_json=None)
    )
    draft.edges.append(GenEdge(source="agent", target="bogus", route=None))
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_response(draft)

    resp = client.post("/api/assist/generate-workflow", json={"description": "drop unknowns"})
    assert resp.status_code == 200, resp.text
    node_ids = {n["id"] for n in resp.json()["graph"]["nodes"]}
    assert "bogus" not in node_ids
    # Edge referencing the dropped node is gone too.
    for edge in resp.json()["graph"]["edges"]:
        assert edge["target"] != "bogus"


def test_generate_workflow_no_api_key_returns_400():
    with patch("app.api.assist.settings.google_api_key", ""):
        resp = client.post("/api/assist/generate-workflow", json={"description": "hi"})
    assert resp.status_code == 400
    assert "GOOGLE_API_KEY" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# suggest-nodes
# ---------------------------------------------------------------------------


def _suggest_graph() -> dict:
    return {
        "nodes": [
            {"id": "trigger", "data": {"label": "T", "nodeType": "trigger"}},
            {"id": "agent", "data": {"label": "A", "nodeType": "agent"}},
            {"id": "end", "data": {"label": "E", "nodeType": "end"}},
        ],
        "edges": [
            {"id": "e1", "source": "trigger", "target": "agent"},
            {"id": "e2", "source": "agent", "target": "end"},
        ],
    }


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_suggest_nodes_caps_and_filters(mock_client_cls):
    assist_service._SUGGEST_CACHE.clear()
    draft = SuggestionsDraft(
        suggestions=[
            {"node_type": "guardrail", "label": "Safety", "reason": "protect output"},
            {"node_type": "evaluation", "label": "Eval", "reason": "score quality"},
            {"node_type": "made_up", "label": "Nope", "reason": "unknown"},
            {"node_type": "summarizer", "label": "Sum", "reason": "shorten"},
            {"node_type": "translator", "label": "Trans", "reason": "localize"},
        ]
    )
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_response(draft)

    resp = client.post(
        "/api/assist/suggest-nodes",
        json={"graph": _suggest_graph(), "selected_node_id": "agent"},
    )
    assert resp.status_code == 200, resp.text
    suggestions = resp.json()["suggestions"]
    assert len(suggestions) <= 3
    assert all(s["node_type"] != "made_up" for s in suggestions)
    assert all(s["default_data"] is None for s in suggestions)


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_suggest_nodes_caches(mock_client_cls):
    assist_service._SUGGEST_CACHE.clear()
    draft = SuggestionsDraft(
        suggestions=[{"node_type": "guardrail", "label": "Safety", "reason": "protect"}]
    )
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_response(draft)

    payload = {"graph": _suggest_graph(), "selected_node_id": "agent"}
    first = client.post("/api/assist/suggest-nodes", json=payload)
    second = client.post("/api/assist/suggest-nodes", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert mock_client.models.generate_content.call_count == 1


# ---------------------------------------------------------------------------
# explain-run
# ---------------------------------------------------------------------------


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_explain_run_failed_returns_fixes(mock_client_cls):
    assist_service._EXPLAIN_CACHE.clear()
    run = _seed_run(status="failed")
    result = ExplainRunResponse(
        explanation_md="The agent node crashed while generating output.",
        suggested_fixes=[{"title": "Check instruction", "detail": "The prompt may be malformed."}],
    )
    mock_client = MagicMock()
    mock_client_cls.return_value = mock_client
    mock_client.models.generate_content.return_value = _mock_response(result)

    resp = client.post("/api/assist/explain-run", json={"run_id": str(run.id)})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["explanation_md"]
    assert body["suggested_fixes"]


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_explain_run_non_failed_returns_400(mock_client_cls):
    run = _seed_run(status="completed", with_nodes=False)
    resp = client.post("/api/assist/explain-run", json={"run_id": str(run.id)})
    assert resp.status_code == 400


@patch("app.api.assist.settings.google_api_key", "test-key")
@patch("app.services.assist.settings.google_api_key", "test-key")
@patch("google.genai.Client")
def test_explain_run_unknown_id_returns_404(mock_client_cls):
    resp = client.post("/api/assist/explain-run", json={"run_id": str(uuid4())})
    assert resp.status_code == 404


def test_explain_run_no_api_key_returns_400():
    run = _seed_run(status="failed")
    with patch("app.api.assist.settings.google_api_key", ""):
        resp = client.post("/api/assist/explain-run", json={"run_id": str(run.id)})
    assert resp.status_code == 400
    assert "GOOGLE_API_KEY" in resp.json()["detail"]
