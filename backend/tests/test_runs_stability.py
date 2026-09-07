from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import valid_graph

client = TestClient(app)


def _create_calculator_workflow() -> dict:
    response = client.post(
        "/api/workflows",
        json={
            "name": "Stability Calculator",
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
    return response.json()


def test_create_run_rejects_empty_input():
    workflow = _create_calculator_workflow()
    response = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow["id"],
            "version_id": workflow["latest_version"]["id"],
            "input_text": "   ",
        },
    )
    assert response.status_code == 400
    assert "input_text" in response.json()["detail"]


def test_create_run_rejects_invalid_graph():
    from uuid import UUID

    from app.db import models
    from app.db.database import SessionLocal

    workflow = _create_calculator_workflow()
    db = SessionLocal()
    try:
        version = (
            db.query(models.WorkflowVersion)
            .filter(models.WorkflowVersion.id == UUID(workflow["latest_version"]["id"]))
            .first()
        )
        assert version is not None
        version.graph_json = {
            "nodes": [
                {"id": "a", "position": {"x": 0, "y": 0}, "data": {"nodeType": "agent"}},
                {"id": "b", "position": {"x": 0, "y": 0}, "data": {"nodeType": "agent"}},
            ],
            "edges": [],
        }
        db.commit()
    finally:
        db.close()

    response = client.post(
        "/api/runs",
        json={
            "workflow_id": workflow["id"],
            "version_id": workflow["latest_version"]["id"],
            "input_text": "hello",
        },
    )
    assert response.status_code == 400