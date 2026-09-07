import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import valid_graph

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_create_and_list_workflow():
    response = client.post(
        "/api/workflows",
        json={
            "name": "Test",
            "graph_json": valid_graph(
                [
                    {
                        "id": "n1",
                        "position": {"x": 0, "y": 0},
                        "data": {"label": "Calc", "nodeType": "tool", "toolType": "calculator"},
                    }
                ],
            ),
        },
    )
    assert response.status_code == 200
    workflow_id = response.json()["id"]

    listed = client.get("/api/workflows")
    assert listed.status_code == 200
    assert any(item["id"] == workflow_id for item in listed.json())


def test_create_run_requires_gemini_for_agent_workflow(monkeypatch):
    monkeypatch.setattr("app.config.settings.google_api_key", "")

    workflow = client.post(
        "/api/workflows",
        json={
            "name": "Agent flow",
            "graph_json": valid_graph(
                [
                    {
                        "id": "n1",
                        "position": {"x": 0, "y": 0},
                        "data": {"label": "Agent", "nodeType": "agent"},
                    }
                ],
            ),
        },
    ).json()

    run_response = client.post(
        "/api/runs",
        json={"workflow_id": workflow["id"], "input_text": "hello"},
    )
    assert run_response.status_code == 400
    assert "GOOGLE_API_KEY" in run_response.json()["detail"]


def test_trigger_workflow_accepts_json_input():
    workflow = client.post(
        "/api/workflows",
        json={
            "name": "Webhook flow",
            "graph_json": valid_graph(
                [
                    {
                        "id": "schema",
                        "position": {"x": 0, "y": 0},
                        "data": {
                            "label": "Input Schema",
                            "nodeType": "input_schema",
                            "inputFields": [{"key": "message", "type": "string", "required": True}],
                        },
                    },
                    {
                        "id": "n1",
                        "position": {"x": 200, "y": 0},
                        "data": {
                            "label": "Transform",
                            "nodeType": "transform",
                            "transformTemplate": "{{input.message}}",
                        },
                    },
                ],
                [
                    {"id": "e1", "source": "schema", "target": "n1"},
                ],
                entry_id="schema",
                exit_id="n1",
            ),
        },
    ).json()

    trigger_response = client.post(
        f"/api/workflows/{workflow['id']}/trigger",
        json={"input": {"message": "hello from webhook"}},
    )
    assert trigger_response.status_code == 200
    body = trigger_response.json()
    assert body["id"]
    assert body["workflow_version_id"] == workflow["latest_version"]["id"]
    assert body["status"] in {"pending", "running", "completed"}
    assert "hello from webhook" in body["input_text"]