"""Tests for MVP2 template publishing + provenance endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.db import models
from app.db.database import SessionLocal
from app.main import app
from app.services.graph_defaults import wrap_graph_with_trigger_end

client = TestClient(app)


def _seed_workflow() -> models.Workflow:
    db = SessionLocal()
    try:
        workflow = models.Workflow(id=uuid4(), user_id=DEFAULT_DEV_USER_ID, name="Template Src")
        db.add(workflow)
        db.flush()
        graph = wrap_graph_with_trigger_end(
            [
                {
                    "id": "n1",
                    "position": {"x": 380, "y": 120},
                    "data": {"label": "Agent", "nodeType": "agent", "instruction": "help"},
                }
            ],
            [],
            entry_id="n1",
            exit_id="n1",
        )
        version = models.WorkflowVersion(
            id=uuid4(), workflow_id=workflow.id, version_number=1, graph_json=graph
        )
        db.add(version)
        db.commit()
        db.refresh(workflow)
        return workflow
    finally:
        db.close()


def test_list_templates_includes_builtins_with_provenance_fields():
    resp = client.get("/api/templates")
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) >= 1
    builtins = [t for t in items if t.get("builtin")]
    assert builtins, "expected built-in templates present"
    sample = builtins[0]
    # Backward-compatible fields.
    assert set(("id", "name", "description", "graph_json")).issubset(sample.keys())
    # Additive provenance fields.
    assert sample["author"] is None
    assert sample["usage_count"] == 0
    assert sample["builtin"] is True


def test_create_template_then_appears_in_list():
    workflow = _seed_workflow()
    resp = client.post(
        "/api/templates",
        json={"name": "My Template", "description": "desc", "workflow_id": str(workflow.id)},
    )
    assert resp.status_code == 200, resp.text
    created = resp.json()
    assert created["name"] == "My Template"
    assert created["builtin"] is False
    assert created["author"] == str(DEFAULT_DEV_USER_ID)
    assert created["usage_count"] == 0
    assert created["graph_json"]["nodes"]

    listed = client.get("/api/templates").json()
    ids = {t["id"] for t in listed}
    assert created["id"] in ids
    # Built-ins still present alongside persisted ones.
    assert any(t.get("builtin") for t in listed)


def test_create_template_unknown_workflow_404():
    resp = client.post(
        "/api/templates",
        json={"name": "X", "workflow_id": str(uuid4())},
    )
    assert resp.status_code == 404


def test_use_persisted_template_increments_usage_and_returns_graph():
    workflow = _seed_workflow()
    created = client.post(
        "/api/templates",
        json={"name": "Usable", "workflow_id": str(workflow.id)},
    ).json()

    resp = client.post(f"/api/templates/{created['id']}/use")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["usage_count"] == 1
    assert body["graph_json"]["nodes"]

    # Second use increments again.
    resp2 = client.post(f"/api/templates/{created['id']}/use")
    assert resp2.json()["usage_count"] == 2


def test_use_builtin_template_returns_graph():
    listed = client.get("/api/templates").json()
    builtin = next(t for t in listed if t.get("builtin"))
    resp = client.post(f"/api/templates/{builtin['id']}/use")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == builtin["id"]
    assert body["graph_json"]["nodes"]
    # Built-in usage is not persisted.
    assert body["usage_count"] == 0


def test_use_unknown_template_404():
    resp = client.post(f"/api/templates/{uuid4()}/use")
    assert resp.status_code == 404
