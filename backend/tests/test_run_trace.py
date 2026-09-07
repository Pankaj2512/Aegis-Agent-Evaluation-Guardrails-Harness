"""Trust-layer Phase 1: GET /api/runs/{id}/trace nested execution trace tree.

Seeds a run with a node result and its llm_call + tool_call child spans, then
asserts the endpoint nests them under a synthesized node span with sane geometry.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.db import models
from app.db.database import SessionLocal
from app.main import app

client = TestClient(app)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _seed_run_with_spans() -> str:
    db = SessionLocal()
    try:
        wf = models.Workflow(id=uuid4(), user_id=DEFAULT_DEV_USER_ID, name="Trace WF")
        db.add(wf)
        db.flush()
        version = models.WorkflowVersion(
            id=uuid4(),
            workflow_id=wf.id,
            version_number=1,
            graph_json={"nodes": [{"id": "agent1", "data": {"label": "LLM Agent"}}], "edges": []},
        )
        db.add(version)
        db.flush()

        start = _utcnow()
        run = models.WorkflowRun(
            id=uuid4(),
            workflow_version_id=version.id,
            status="completed",
            input_text="hi",
            final_output="done",
            started_at=start,
            completed_at=start + timedelta(milliseconds=2100),
        )
        db.add(run)
        db.flush()

        # One agent node that took 2100ms (created_at = end of node).
        db.add(
            models.NodeResult(
                id=uuid4(),
                run_id=run.id,
                node_id="agent1",
                node_type="agent",
                node_label="LLM Agent",
                status="completed",
                output="done",
                latency_ms=2100,
                created_at=start + timedelta(milliseconds=2100),
            )
        )

        base_wall = 1_000_000.0
        # Two children of the agent node, out of chronological order on purpose:
        # a tool_call started later than the first llm_call.
        db.add(
            models.RunSpan(
                id=uuid4(),
                run_id=run.id,
                node_id="agent1",
                kind="tool_call",
                name="kb_retrieve",
                status="completed",
                duration_ms=900,
                attributes_json={"args": '{"q":"x"}', "result": "ctx", "started_wall": base_wall + 0.5},
            )
        )
        db.add(
            models.RunSpan(
                id=uuid4(),
                run_id=run.id,
                node_id="agent1",
                kind="llm_call",
                name="gemini-2.5-flash",
                status="completed",
                duration_ms=400,
                cost_usd=0.0001,
                tokens_json={"prompt": 1200, "completion": 800, "total": 2000},
                attributes_json={"prompt": "p", "completion": "c", "started_wall": base_wall},
            )
        )
        db.commit()
        return str(run.id)
    finally:
        db.close()


def test_trace_nests_llm_and_tool_children_under_node():
    run_id = _seed_run_with_spans()
    resp = client.get(f"/api/runs/{run_id}/trace")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["run_id"] == run_id
    assert body["status"] == "completed"
    assert body["total_duration_ms"] == 2100
    assert len(body["spans"]) == 1

    node = body["spans"][0]
    assert node["kind"] == "node"
    assert node["name"] == "LLM Agent"
    assert node["node_id"] == "agent1"
    assert node["duration_ms"] == 2100
    assert node["offset_ms"] >= 0

    children = node["children"]
    assert len(children) == 2
    # Ordered chronologically by captured start (llm_call started first).
    assert [c["kind"] for c in children] == ["llm_call", "tool_call"]

    llm = children[0]
    assert llm["name"] == "gemini-2.5-flash"
    assert llm["duration_ms"] == 400
    assert llm["tokens"] == {"prompt": 1200, "completion": 800, "total": 2000}
    assert llm["cost_usd"] == 0.0001
    assert llm["parent_span_id"] == "node:agent1"
    # started_wall is an internal ordering key — must not leak into attributes.
    assert "started_wall" not in (llm["attributes"] or {})
    assert (llm["attributes"] or {}).get("prompt") == "p"

    tool = children[1]
    assert tool["name"] == "kb_retrieve"
    assert tool["duration_ms"] == 900
    # Tool started 0.5s after the llm call -> larger run-relative offset.
    assert tool["offset_ms"] >= llm["offset_ms"]


def test_trace_empty_for_run_without_spans():
    db = SessionLocal()
    try:
        wf = models.Workflow(id=uuid4(), user_id=DEFAULT_DEV_USER_ID, name="Empty Trace WF")
        db.add(wf)
        db.flush()
        version = models.WorkflowVersion(
            id=uuid4(), workflow_id=wf.id, version_number=1, graph_json={"nodes": [], "edges": []}
        )
        db.add(version)
        db.flush()
        run = models.WorkflowRun(
            id=uuid4(), workflow_version_id=version.id, status="completed", input_text="hi"
        )
        db.add(run)
        db.commit()
        run_id = str(run.id)
    finally:
        db.close()

    resp = client.get(f"/api/runs/{run_id}/trace")
    assert resp.status_code == 200, resp.text
    assert resp.json()["spans"] == []
