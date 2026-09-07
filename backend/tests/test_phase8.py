from app.services.schedule_worker import count_scheduled_workflows, scheduler_status


def test_scheduler_status_shape():
    status = scheduler_status()
    assert "enabled" in status
    assert "running" in status
    assert "poll_seconds" in status


def test_count_scheduled_workflows():
    graphs = [
        {
            "nodes": [
                {"id": "trigger", "data": {"nodeType": "trigger", "triggerType": "schedule", "scheduleCron": "0 * * * *"}},
                {"id": "end", "data": {"nodeType": "end"}},
            ],
            "edges": [],
        },
        {
            "nodes": [
                {"id": "trigger", "data": {"nodeType": "trigger", "triggerType": "manual"}},
                {"id": "end", "data": {"nodeType": "end"}},
            ],
            "edges": [],
        },
    ]
    assert count_scheduled_workflows(graphs) == 1


def test_health_includes_scheduler():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert "scheduler" in response.json()