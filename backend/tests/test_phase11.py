from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.services.guardrail import validate_content
from app.services.quality_metrics import aggregate_quality_metrics, apply_eval_threshold

client = TestClient(app)


def test_validate_required_keywords():
    result = validate_content("hello world", {"required_keywords": ["hello", "team"]})
    assert not result.passed
    assert "team" in result.message


def test_validate_min_length():
    result = validate_content("hi", {"min_length": 5})
    assert not result.passed


def test_validate_blocked_patterns():
    result = validate_content("password=secret", {"blocked_patterns": [r"password\s*="]})
    assert not result.passed


def test_apply_eval_threshold_pass_and_fail():
    metadata = {"eval1": {"eval_threshold": 3.5}}
    passing = [{"node_id": "eval1", "aggregate_score": 4.0, "faithfulness": 4}]
    assert apply_eval_threshold(passing, metadata) is True
    assert passing[0]["passed"] is True

    failing = [{"node_id": "eval1", "aggregate_score": 2.5, "faithfulness": 2}]
    assert apply_eval_threshold(failing, metadata) is False
    assert failing[0]["passed"] is False


def test_aggregate_quality_metrics_from_runs():
    runs = [
        SimpleNamespace(
            id="r1",
            status="completed",
            created_at=SimpleNamespace(isoformat=lambda: "2026-06-30T10:00:00"),
            version=SimpleNamespace(
                workflow=SimpleNamespace(id="wf1", name="Support Bot")
            ),
            metrics_json={
                "eval_aggregate": 4.2,
                "eval_passed": True,
                "eval_scores": [
                    {
                        "faithfulness": 5,
                        "helpfulness": 4,
                        "relevance": 4,
                        "toxicity": 1,
                        "aggregate_score": 4.2,
                    }
                ],
                "guardrail_events": [
                    {"node_id": "g1", "status": "passed"},
                    {"node_id": "g2", "status": "warned"},
                ],
            },
        ),
        SimpleNamespace(
            id="r2",
            status="failed",
            created_at=SimpleNamespace(isoformat=lambda: "2026-06-30T11:00:00"),
            version=SimpleNamespace(
                workflow=SimpleNamespace(id="wf1", name="Support Bot")
            ),
            metrics_json={
                "guardrail_blocked": True,
                "failed_guardrails": ["g1"],
                "guardrail_events": [
                    {"node_id": "g1", "status": "failed"},
                ],
            },
        ),
    ]

    quality = aggregate_quality_metrics(runs)
    assert quality["eval_run_count"] == 1
    assert quality["eval_pass_count"] == 1
    assert quality["guardrail_stats"]["blocked_runs"] == 1
    assert quality["guardrail_stats"]["warned"] == 1
    assert quality["guardrail_stats"]["failed"] == 1
    assert len(quality["eval_trend"]) == 1
    assert quality["workflow_eval_leaderboard"][0]["workflow_name"] == "Support Bot"


def test_observability_summary_includes_quality():
    response = client.get("/api/observability/summary")
    assert response.status_code == 200
    body = response.json()
    assert "quality" in body
    assert "guardrail_stats" in body["quality"]
    assert "eval_trend" in body["quality"]
    if body["recent_runs"]:
        assert "workflow_name" in body["recent_runs"][0]