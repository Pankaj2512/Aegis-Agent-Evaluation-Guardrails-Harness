from fastapi.testclient import TestClient

from app.main import app
from app.services.quality_metrics import (
    aggregate_workflow_quality,
    detect_eval_regression,
    extract_graph_quality_config,
)
from tests.conftest import valid_graph

client = TestClient(app)


def test_detect_eval_regression_flags_drop():
    trend = [
        {"run_id": "1", "created_at": "2026-06-28T10:00:00", "aggregate": 4.5},
        {"run_id": "2", "created_at": "2026-06-28T11:00:00", "aggregate": 4.3},
        {"run_id": "3", "created_at": "2026-06-28T12:00:00", "aggregate": 4.4},
        {"run_id": "4", "created_at": "2026-06-28T13:00:00", "aggregate": 2.8},
    ]
    regression = detect_eval_regression(trend)
    assert regression is not None
    assert regression["detected"] is True
    assert regression["delta"] < 0


def test_extract_graph_quality_config():
    graph = valid_graph(
        [
            {
                "id": "eval1",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "RAG Eval",
                    "nodeType": "evaluation",
                    "evalPreset": "rag_quality",
                    "evalThreshold": 3.5,
                },
            },
            {
                "id": "g1",
                "position": {"x": 200, "y": 0},
                "data": {
                    "label": "Output Guard",
                    "nodeType": "guardrail",
                    "rules": {"mode": "output", "detect_pii": True},
                },
            },
        ],
        entry_id="eval1",
        exit_id="g1",
    )
    config = extract_graph_quality_config(graph)
    assert config["eval_node_count"] == 1
    assert config["guardrail_node_count"] == 1
    assert config["eval_nodes"][0]["threshold"] == 3.5


def test_guardrail_preview_endpoint():
    response = client.post(
        "/api/meta/guardrail-preview",
        json={
            "text": "contact me at user@example.com",
            "rules": {"detect_pii": True, "fail_behavior": "block"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["passed"] is False
    assert body["would_block"] is True


def test_workflow_quality_endpoint():
    graph = valid_graph(
        [
            {
                "id": "eval1",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "Eval",
                    "nodeType": "evaluation",
                    "evalThreshold": 4.0,
                },
            },
        ],
        entry_id="eval1",
        exit_id="eval1",
    )
    created = client.post(
        "/api/workflows",
        json={"name": "Quality Flow", "graph_json": graph},
    ).json()

    response = client.get(f"/api/workflows/{created['id']}/quality")
    assert response.status_code == 200
    body = response.json()
    assert body["workflow_name"] == "Quality Flow"
    assert body["graph_config"]["eval_node_count"] == 1
    assert "guardrail_stats" in body


def test_aggregate_workflow_quality_empty_runs():
    graph = valid_graph(
        [
            {
                "id": "n1",
                "position": {"x": 0, "y": 0},
                "data": {"label": "Agent", "nodeType": "agent"},
            }
        ],
    )
    quality = aggregate_workflow_quality([], graph)
    assert quality["eval_run_count"] == 0
    assert quality["eval_regression"] is None