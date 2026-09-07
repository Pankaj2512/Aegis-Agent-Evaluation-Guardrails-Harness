"""Tests for the ephemeral node-test and expression-preview endpoints.

No test makes a real Gemini call: the LLM-family paths are exercised either with
an empty key (clean no-key failure) or with google.genai.Client patched to raise
(invalid-key failure). Both assert the graceful "failed" contract, never a 500.
"""

from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.config import settings
from app.db import models
from app.db.database import SessionLocal
from app.main import app

from tests.conftest import valid_graph

client = TestClient(app)


# ---------------------------------------------------------------------------
# seeding helpers
# ---------------------------------------------------------------------------


def _seed_workflow(graph: dict, *, user_id=DEFAULT_DEV_USER_ID) -> str:
    db = SessionLocal()
    try:
        workflow = models.Workflow(id=uuid4(), user_id=user_id, name="Node Test Flow")
        db.add(workflow)
        db.flush()
        version = models.WorkflowVersion(
            id=uuid4(),
            workflow_id=workflow.id,
            version_number=1,
            graph_json=graph,
        )
        db.add(version)
        db.commit()
        return str(workflow.id)
    finally:
        db.close()


def _seed_run(
    workflow_id: str,
    *,
    input_text: str = "do the thing",
    final_output: str | None = "hello world",
    node_outputs: dict[str, str] | None = None,
) -> str:
    db = SessionLocal()
    try:
        version = (
            db.query(models.WorkflowVersion)
            .filter(models.WorkflowVersion.workflow_id == UUID(workflow_id))
            .order_by(models.WorkflowVersion.version_number.desc())
            .first()
        )
        run = models.WorkflowRun(
            id=uuid4(),
            workflow_version_id=version.id,
            status="completed",
            input_text=input_text,
            final_output=final_output,
        )
        db.add(run)
        db.flush()
        for node_id, output in (node_outputs or {}).items():
            db.add(
                models.NodeResult(
                    id=uuid4(),
                    run_id=run.id,
                    node_id=node_id,
                    node_type="agent",
                    node_label=node_id,
                    status="completed",
                    output=output,
                )
            )
        db.commit()
        return str(run.id)
    finally:
        db.close()


def _transform_workflow(template: str) -> tuple[str, str]:
    node = {
        "id": "xform",
        "position": {"x": 400, "y": 120},
        "data": {"label": "Transform", "nodeType": "transform", "template": template},
    }
    return _seed_workflow(valid_graph([node])), "xform"


# ---------------------------------------------------------------------------
# node-test: handler happy paths
# ---------------------------------------------------------------------------


def test_node_test_transform_happy_path():
    workflow_id, node_id = _transform_workflow("Echo: {{input.text}}")
    resp = client.post(
        f"/api/workflows/{workflow_id}/node-test",
        json={"node_id": node_id, "input_text": "hi", "extra_context": None},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["node_id"] == node_id
    assert body["status"] == "completed"
    assert body["output"] == "Echo: hi"
    assert body["error"] is None
    assert body["latency_ms"] >= 0


def test_node_test_json_parse_happy_path():
    node = {
        "id": "jp",
        "position": {"x": 400, "y": 120},
        "data": {"label": "JSON", "nodeType": "json_parse", "jsonPath": "name"},
    }
    workflow_id = _seed_workflow(valid_graph([node]))
    resp = client.post(
        f"/api/workflows/{workflow_id}/node-test",
        json={"node_id": "jp", "input_text": '{"name": "Ada", "age": 36}'},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["output"] == "Ada"


def test_node_test_steps_context_simulation():
    workflow_id, node_id = _transform_workflow("{{steps.up.output}}!")
    resp = client.post(
        f"/api/workflows/{workflow_id}/node-test",
        json={
            "node_id": node_id,
            "input_text": "ignored",
            "extra_context": {"steps": {"up": "done"}},
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "completed"
    assert body["output"] == "done!"


# ---------------------------------------------------------------------------
# node-test: unsupported / errors
# ---------------------------------------------------------------------------


def test_node_test_unsupported_type():
    workflow_id, _ = _transform_workflow("{{input.text}}")
    resp = client.post(
        f"/api/workflows/{workflow_id}/node-test",
        json={"node_id": "trigger", "input_text": "x"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "unsupported"
    assert body["output"] is None
    assert body["error"]


def test_node_test_unknown_node_404():
    workflow_id, _ = _transform_workflow("{{input.text}}")
    resp = client.post(
        f"/api/workflows/{workflow_id}/node-test",
        json={"node_id": "does-not-exist", "input_text": "x"},
    )
    assert resp.status_code == 404


def test_node_test_unknown_workflow_404():
    resp = client.post(
        f"/api/workflows/{uuid4()}/node-test",
        json={"node_id": "x", "input_text": "y"},
    )
    assert resp.status_code == 404


def test_node_test_oversize_400():
    workflow_id, node_id = _transform_workflow("{{input.text}}")
    resp = client.post(
        f"/api/workflows/{workflow_id}/node-test",
        json={"node_id": node_id, "input_text": "x" * (32 * 1024 + 1)},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# node-test: LLM-family graceful failure (never a real API call)
# ---------------------------------------------------------------------------


def _agent_workflow() -> tuple[str, str]:
    node = {
        "id": "agent",
        "position": {"x": 400, "y": 120},
        "data": {"label": "Agent", "nodeType": "agent", "instruction": "Say hello."},
    }
    return _seed_workflow(valid_graph([node])), "agent"


def test_node_test_llm_missing_key_failed(monkeypatch):
    monkeypatch.setattr(settings, "google_api_key", "")
    workflow_id, node_id = _agent_workflow()
    resp = client.post(
        f"/api/workflows/{workflow_id}/node-test",
        json={"node_id": node_id, "input_text": "hi"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "failed"
    assert body["output"] is None
    assert "GOOGLE_API_KEY" in body["error"]


def test_node_test_llm_invalid_key_failed():
    workflow_id, node_id = _agent_workflow()
    with patch("google.genai.Client", side_effect=RuntimeError("API key not valid")):
        resp = client.post(
            f"/api/workflows/{workflow_id}/node-test",
            json={"node_id": node_id, "input_text": "hi"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "failed"
    assert body["output"] is None
    assert "API key not valid" in body["error"]


# ---------------------------------------------------------------------------
# expression-preview
# ---------------------------------------------------------------------------


def test_expression_preview_from_run_steps_resolution():
    workflow_id, _ = _transform_workflow("{{input.text}}")
    run_id = _seed_run(
        workflow_id,
        input_text="the input",
        final_output="final answer",
        node_outputs={"agent": "hello world"},
    )
    resp = client.post(
        f"/api/workflows/{workflow_id}/expression-preview",
        json={"expression": "{{steps.agent.output}}", "run_id": run_id},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rendered"] == "hello world"
    assert body["error"] is None
    assert body["run_id"] == run_id
    assert body["context_available"]["input"] is True
    assert body["context_available"]["last_output"] is True
    assert "agent" in body["context_available"]["steps"]


def test_expression_preview_most_recent_run_when_no_run_id():
    workflow_id, _ = _transform_workflow("{{input.text}}")
    run_id = _seed_run(workflow_id, final_output="latest out", node_outputs={})
    resp = client.post(
        f"/api/workflows/{workflow_id}/expression-preview",
        json={"expression": "{{last_output}}", "run_id": None, "sample_input": "unused"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rendered"] == "latest out"
    assert body["run_id"] == run_id


def test_expression_preview_sample_input_fallback():
    workflow_id, _ = _transform_workflow("{{input.text}}")  # no runs seeded
    resp = client.post(
        f"/api/workflows/{workflow_id}/expression-preview",
        json={"expression": "Hi {{input.text}}", "run_id": None, "sample_input": "there"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rendered"] == "Hi there"
    assert body["run_id"] is None
    assert body["context_available"]["steps"] == []


def test_expression_preview_render_error_is_data_not_500():
    workflow_id, _ = _transform_workflow("{{input.text}}")
    with patch(
        "app.services.node_test.render_template", side_effect=ValueError("boom")
    ):
        resp = client.post(
            f"/api/workflows/{workflow_id}/expression-preview",
            json={"expression": "{{input.text}}", "sample_input": "x"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rendered"] is None
    assert body["error"] == "boom"


def test_expression_preview_run_ownership_404_wrong_workflow():
    workflow_a, _ = _transform_workflow("{{input.text}}")
    workflow_b, _ = _transform_workflow("{{input.text}}")
    run_b = _seed_run(workflow_b, node_outputs={})
    # A run that belongs to workflow B must not resolve under workflow A.
    resp = client.post(
        f"/api/workflows/{workflow_a}/expression-preview",
        json={"expression": "{{last_output}}", "run_id": run_b},
    )
    assert resp.status_code == 404


def test_expression_preview_oversize_expression_400():
    workflow_id, _ = _transform_workflow("{{input.text}}")
    resp = client.post(
        f"/api/workflows/{workflow_id}/expression-preview",
        json={"expression": "x" * (8 * 1024 + 1), "sample_input": "y"},
    )
    assert resp.status_code == 400
