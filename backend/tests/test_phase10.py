from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.services.cron_utils import cron_is_valid, cron_next_runs
from app.services.schedule_info import is_scheduled_run_input, schedule_info_for_graph
from tests.conftest import valid_graph

client = TestClient(app)


def test_cron_next_runs_returns_future_datetimes():
    runs = cron_next_runs("0 * * * *", count=2)
    assert len(runs) == 2
    assert runs[0] < runs[1]


def test_cron_is_valid_rejects_garbage():
    assert cron_is_valid("0 9 * * *") is True
    assert cron_is_valid("not a cron") is False


def test_is_scheduled_run_input():
    assert is_scheduled_run_input('{"scheduled": true, "trigger": "cron"}') is True
    assert is_scheduled_run_input('{"message": "hi"}') is False


def test_schedule_info_for_graph():
    graph = valid_graph(
        [
            {
                "id": "n1",
                "position": {"x": 200, "y": 0},
                "data": {"label": "Agent", "nodeType": "agent"},
            }
        ],
        trigger_type="schedule",
        schedule_cron="0 9 * * *",
    )

    info = schedule_info_for_graph(
        "00000000-0000-0000-0000-000000000099",
        "Digest",
        graph,
        last_fired_at=datetime(2026, 6, 30, 9, 0, tzinfo=timezone.utc),
    )
    assert info is not None
    assert info["cron"] == "0 9 * * *"
    assert info["cron_valid"] is True
    assert info["next_run_at"]
    assert info["last_fired_at"]


def test_cron_preview_endpoint():
    response = client.get("/api/meta/cron-preview", params={"expr": "0 9 * * *", "count": 2})
    assert response.status_code == 200
    body = response.json()
    assert len(body["next_runs"]) == 2


def test_list_scheduled_workflows_endpoint():
    graph = valid_graph(
        [
            {
                "id": "n1",
                "position": {"x": 200, "y": 0},
                "data": {"label": "Agent", "nodeType": "agent"},
            }
        ],
        trigger_type="schedule",
        schedule_cron="0 12 * * *",
    )

    created = client.post(
        "/api/workflows",
        json={"name": "Cron Flow", "graph_json": graph},
    ).json()

    listed = client.get("/api/workflows/schedules")
    assert listed.status_code == 200
    rows = listed.json()
    assert any(row["workflow_id"] == created["id"] for row in rows)
    match = next(row for row in rows if row["workflow_id"] == created["id"])
    assert match["cron"] == "0 12 * * *"
    assert match["next_run_at"]


def test_get_workflow_schedule_endpoint():
    graph = valid_graph(
        [
            {
                "id": "n1",
                "position": {"x": 200, "y": 0},
                "data": {"label": "Transform", "nodeType": "transform", "transformTemplate": "x"},
            }
        ],
        trigger_type="schedule",
        schedule_cron="*/30 * * * *",
    )

    created = client.post(
        "/api/workflows",
        json={"name": "Half Hourly", "graph_json": graph},
    ).json()

    response = client.get(f"/api/workflows/{created['id']}/schedule")
    assert response.status_code == 200
    assert response.json()["cron"] == "*/30 * * * *"


def test_observability_includes_scheduled_workflows():
    response = client.get("/api/observability/summary")
    assert response.status_code == 200
    assert "scheduled_workflows" in response.json()