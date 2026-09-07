from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.db import models
from app.db.database import SessionLocal
from app.main import app
from app.services.compiler import compile_workflow
from app.services.observability_events import broadcast_observability_event, subscribe_observability
from app.services.schedule_sync import sync_workflow_schedule
from tests.conftest import valid_graph

client = TestClient(app)


def test_sync_workflow_schedule_upserts_row():
    db = SessionLocal()
    try:
        workflow = models.Workflow(id=uuid4(), user_id=DEFAULT_DEV_USER_ID, name="Cron Flow")
        db.add(workflow)
        db.flush()
        graph_json = valid_graph(
            [
                {
                    "id": "agent",
                    "position": {"x": 200, "y": 0},
                    "data": {"label": "Agent", "nodeType": "agent"},
                },
            ],
            trigger_type="schedule",
            schedule_cron="0 * * * *",
        )
        version = models.WorkflowVersion(
            id=uuid4(),
            workflow_id=workflow.id,
            version_number=1,
            graph_json=graph_json,
        )
        db.add(version)
        db.flush()

        sync_workflow_schedule(
            db,
            workflow_id=workflow.id,
            version_id=version.id,
            graph_json=version.graph_json,
        )
        db.commit()

        row = (
            db.query(models.WorkflowSchedule)
            .filter(models.WorkflowSchedule.workflow_id == workflow.id)
            .first()
        )
        assert row is not None
        assert row.cron_expr == "0 * * * *"
        assert row.cron_valid is True
    finally:
        db.close()


def test_compile_guardrail_route_metadata():
    graph = valid_graph(
        [
            {
                "id": "g1",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "Route Guard",
                    "nodeType": "guardrail",
                    "rules": {
                        "fail_behavior": "route",
                        "pass_route": "ok",
                        "failure_route": "reject",
                    },
                },
            },
            {
                "id": "ok_agent",
                "position": {"x": 200, "y": 0},
                "data": {"label": "OK path", "nodeType": "agent"},
            },
            {
                "id": "fail_agent",
                "position": {"x": 400, "y": 0},
                "data": {"label": "Reject path", "nodeType": "agent"},
            },
        ],
        edges=[
            {"id": "e1", "source": "g1", "target": "ok_agent", "label": "ok", "data": {"route": "ok"}},
            {"id": "e2", "source": "g1", "target": "fail_agent", "label": "reject", "data": {"route": "reject"}},
            {"id": "e3", "source": "ok_agent", "target": "fail_agent"},
        ],
        entry_id="g1",
        exit_id="fail_agent",
    )
    _workflow, metadata, _ = compile_workflow(graph)
    assert metadata["g1"]["is_branch"] is True
    assert metadata["g1"]["routes"] == ["ok", "reject"]


@pytest.mark.asyncio
async def test_broadcast_observability_event():
    queue = subscribe_observability("user-test")
    await broadcast_observability_event(
        "user-test",
        {"type": "run_completed", "run_id": "abc", "status": "completed"},
    )
    event = await queue.get()
    assert event["run_id"] == "abc"


def test_observability_stream_route_registered():
    openapi = client.get("/openapi.json").json()
    assert "/api/observability/stream" in openapi["paths"]