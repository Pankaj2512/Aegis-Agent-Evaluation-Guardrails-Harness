"""Tests for MVP2 backend foundation: timeline, deploy, dashboards, crypto, cost alerts."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import valid_graph

client = TestClient(app)


def _make_workflow(name: str, nodes: list, edges: list | None = None, **kwargs) -> dict:
    return client.post(
        "/api/workflows",
        json={"name": name, "graph_json": valid_graph(nodes, edges or [], **kwargs)},
    ).json()


# ---------------------------------------------------------------------------
# Item 5: GET /api/runs/{run_id}/timeline
# ---------------------------------------------------------------------------


def test_run_timeline_returns_waterfall_offsets():
    # Ingest a run with node events (gives NodeResults with latency).
    ingest = client.post(
        "/v1/ingest/runs",
        json={
            "workflow_name": "Timeline WF",
            "input": "hi",
            "output": "done",
            "status": "completed",
            "latency_ms": 900,
            "node_events": [
                {"node_id": "a", "label": "First", "node_type": "agent", "latency_ms": 300},
                {"node_id": "b", "label": "Second", "node_type": "transform", "latency_ms": 500},
            ],
        },
    )
    assert ingest.status_code == 201, ingest.text
    run_id = ingest.json()["run_id"]

    resp = client.get(f"/api/runs/{run_id}/timeline")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["run_id"] == run_id
    assert body["status"] == "completed"
    assert len(body["nodes"]) == 2
    for node in body["nodes"]:
        assert set(node) == {
            "node_id",
            "node_type",
            "label",
            "status",
            "latency_ms",
            "start_offset_ms",
            "duration_ms",
        }
        assert node["start_offset_ms"] >= 0
        assert node["duration_ms"] >= 0
    # Duration reflects latency.
    by_id = {n["node_id"]: n for n in body["nodes"]}
    assert by_id["a"]["duration_ms"] == 300
    assert by_id["b"]["duration_ms"] == 500


def test_run_timeline_not_found():
    resp = client.get(f"/api/runs/{uuid.uuid4()}/timeline")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Item 6: GET /api/workflows/{workflow_id}/deploy
# ---------------------------------------------------------------------------


def test_deploy_descriptor_requires_published_version():
    wf = _make_workflow(
        "Deploy WF",
        [{"id": "n1", "position": {"x": 0, "y": 0}, "data": {"label": "T", "nodeType": "tool", "toolType": "calculator"}}],
    )
    # No published version yet → 409.
    resp = client.get(f"/api/workflows/{wf['id']}/deploy")
    assert resp.status_code == 409


def test_deploy_descriptor_after_publish_includes_mcp_tool():
    wf = _make_workflow(
        "Deploy WF Published",
        [
            {
                "id": "schema",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "Input Schema",
                    "nodeType": "input_schema",
                    "inputFields": [{"key": "topic", "type": "string", "required": True}],
                },
            },
            {
                "id": "n1",
                "position": {"x": 200, "y": 0},
                "data": {"label": "Transform", "nodeType": "transform", "transformTemplate": "{{input.topic}}"},
            },
        ],
        [{"id": "e1", "source": "schema", "target": "n1"}],
        entry_id="schema",
        exit_id="n1",
    )
    version_id = wf["latest_version"]["id"]

    publish = client.post(f"/api/workflows/{wf['id']}/publish", json={"version_id": version_id})
    assert publish.status_code == 200, publish.text

    resp = client.get(f"/api/workflows/{wf['id']}/deploy")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["invoke_path"] == f"/v1/workflows/{wf['id']}/invoke"
    assert body["method"] == "POST"
    assert "curl" in body and "invoke" in body["curl"]
    tool = body["mcp_tool"]
    assert tool["name"].startswith("invoke_")
    schema = tool["input_schema"]
    assert schema["type"] == "object"
    assert "topic" in schema["properties"]
    assert schema["required"] == ["topic"]


# ---------------------------------------------------------------------------
# Item 7: GET /api/observability/dashboards + cost alert
# ---------------------------------------------------------------------------


def test_observability_dashboards_breakdowns_and_percentiles():
    client.post(
        "/v1/ingest/runs",
        json={
            "workflow_name": "Dash WF",
            "input": "x",
            "output": "y",
            "status": "completed",
            "latency_ms": 1200,
            "total_cost_usd": 0.02,
            "total_tokens": 500,
            "node_events": [{"node_id": "a", "node_type": "agent", "latency_ms": 400}],
        },
    )
    resp = client.get("/api/observability/dashboards")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    for key in ("run_count", "status_counts", "latency_ms", "by_workflow", "by_node_type", "by_model", "filters"):
        assert key in body
    assert set(body["latency_ms"]) == {"p50", "p95", "p99", "sample_size"}
    # node_type dimension picked up the agent node.
    node_types = {row["node_type"] for row in body["by_node_type"]}
    assert "agent" in node_types


def test_observability_dashboards_status_filter():
    resp = client.get("/api/observability/dashboards", params={"status": "completed"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["filters"]["status"] == "completed"
    assert set(body["status_counts"]) <= {"completed"}


def test_observability_dashboards_rejects_bad_date():
    resp = client.get("/api/observability/dashboards", params={"start_date": "not-a-date"})
    assert resp.status_code == 400


def test_cost_alert_rule_is_supported():
    # cost_usd must be an accepted alert metric (wired through the alert path).
    wf = _make_workflow(
        "Cost Alert WF",
        [{"id": "n1", "position": {"x": 0, "y": 0}, "data": {"label": "T", "nodeType": "tool", "toolType": "calculator"}}],
    )
    resp = client.post(
        "/api/alerts",
        json={"workflow_id": wf["id"], "metric": "cost_usd", "operator": "gt", "threshold": 1.0},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["metric"] == "cost_usd"


# ---------------------------------------------------------------------------
# Item 2: credential secret encryption at rest
# ---------------------------------------------------------------------------


def test_credential_secret_encrypted_at_rest(monkeypatch):
    from cryptography.fernet import Fernet
    from uuid import uuid4

    key = Fernet.generate_key().decode()
    monkeypatch.setattr("app.config.settings.app_encryption_key", key)
    # crypto reads settings live, so no cache to bust.

    # Unique name so re-runs against the persistent test DB never collide.
    name = f"pg-enc-{uuid4().hex[:8]}"
    created = client.post(
        "/api/credentials",
        json={"name": name, "type": "postgres", "config": {"connection_url": "postgres://u:p@h/db"}},
    )
    assert created.status_code == 200, created.text
    # Response is masked.
    assert created.json()["config"]["connection_url"] == "••••••••"

    # Stored value is encrypted (v1: prefix), and resolve() decrypts it back.
    from app.db.database import SessionLocal
    from app.db import models
    from app.services.credentials import resolve_credential

    db = SessionLocal()
    try:
        row = db.query(models.Credential).filter(models.Credential.name == name).first()
        assert row is not None
        assert row.config["connection_url"].startswith("v1:")
        assert resolve_credential(row)["connection_url"] == "postgres://u:p@h/db"
    finally:
        db.close()


def test_credential_secret_plaintext_without_key(monkeypatch):
    from uuid import uuid4

    monkeypatch.setattr("app.config.settings.app_encryption_key", "")

    name = f"pg-plain-{uuid4().hex[:8]}"
    created = client.post(
        "/api/credentials",
        json={"name": name, "type": "postgres", "config": {"connection_url": "postgres://u:p@h/db2"}},
    )
    assert created.status_code == 200, created.text

    from app.db.database import SessionLocal
    from app.db import models

    db = SessionLocal()
    try:
        row = db.query(models.Credential).filter(models.Credential.name == name).first()
        # Graceful degradation: stored plaintext (not crashing) when no key.
        assert row.config["connection_url"] == "postgres://u:p@h/db2"
    finally:
        db.close()
