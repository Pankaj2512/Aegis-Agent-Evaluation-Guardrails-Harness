from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.db import models
from app.db.database import SessionLocal
from app.main import app
from app.services.compiler import compile_workflow
from app.services.eval import EvalThresholdBlockedError
from app.services.guardrail import GuardrailResult, validate_guardrail_content
from app.services.quality_alerts import quality_webhook_for_run
from tests.conftest import valid_graph

client = TestClient(app)


def _seed_quality_run(
    *,
    eval_aggregate: float | None = None,
    eval_passed: bool | None = None,
    guardrail_blocked: bool = False,
    status: str = "completed",
) -> models.WorkflowRun:
    db = SessionLocal()
    try:
        workflow = models.Workflow(
            id=uuid4(),
            user_id=DEFAULT_DEV_USER_ID,
            name="Quality Filter Flow",
        )
        db.add(workflow)
        db.flush()

        version = models.WorkflowVersion(
            id=uuid4(),
            workflow_id=workflow.id,
            version_number=1,
            graph_json={"nodes": [], "edges": []},
        )
        db.add(version)
        db.flush()

        metrics: dict = {}
        if eval_aggregate is not None:
            metrics["eval_aggregate"] = eval_aggregate
        if eval_passed is not None:
            metrics["eval_passed"] = eval_passed
        if guardrail_blocked:
            metrics["guardrail_blocked"] = True
            metrics["failed_guardrails"] = ["g1"]

        run = models.WorkflowRun(
            id=uuid4(),
            workflow_version_id=version.id,
            status=status,
            input_text="quality test",
            metrics_json=metrics or None,
            created_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()


def test_compile_quality_enforcement_metadata():
    graph = valid_graph(
        [
            {
                "id": "eval1",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "Eval",
                    "nodeType": "evaluation",
                    "evalThreshold": 4.0,
                    "evalFailBehavior": "block",
                },
            },
            {
                "id": "g1",
                "position": {"x": 200, "y": 0},
                "data": {
                    "label": "LLM Guard",
                    "nodeType": "guardrail",
                    "rules": {
                        "guardrail_type": "llm",
                        "llm_instruction": "Reject toxic content",
                        "fail_behavior": "block",
                    },
                },
            },
        ],
        edges=[{"id": "e1", "source": "eval1", "target": "g1"}],
        entry_id="eval1",
        exit_id="g1",
    )
    _workflow, metadata, _ = compile_workflow(graph)
    assert metadata["eval1"]["eval_fail_behavior"] == "block"
    assert metadata["eval1"]["eval_threshold"] == 4.0
    assert metadata["g1"]["guardrail_type"] == "llm"


def test_eval_threshold_blocked_error_carries_aggregate():
    exc = EvalThresholdBlockedError("below threshold", "eval1", 2.8)
    assert exc.node_id == "eval1"
    assert exc.aggregate == 2.8


def test_validate_guardrail_content_routes_llm_engine():
    with patch("app.services.guardrail.validate_content_llm") as mock_llm:
        mock_llm.return_value = GuardrailResult(
            passed=False,
            message="Policy violation",
            severity="error",
        )
        result = validate_guardrail_content(
            "unsafe content",
            {"guardrail_type": "llm", "llm_instruction": "Block unsafe text"},
        )
        mock_llm.assert_called_once()
        assert result.passed is False


def test_guardrail_preview_llm_engine():
    with patch("app.services.guardrail.validate_content_llm") as mock_llm:
        mock_llm.return_value = GuardrailResult(
            passed=False,
            message="LLM rejected content",
            severity="error",
        )
        response = client.post(
            "/api/meta/guardrail-preview",
            json={
                "text": "bad output",
                "rules": {"guardrail_type": "llm", "fail_behavior": "block"},
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["passed"] is False
        assert body["would_block"] is True


def test_list_runs_quality_filters():
    passing = _seed_quality_run(eval_aggregate=4.2, eval_passed=True)
    failing = _seed_quality_run(eval_aggregate=2.1, eval_passed=False)
    blocked = _seed_quality_run(guardrail_blocked=True, status="failed")
    plain = _seed_quality_run()

    eval_failed = client.get("/api/runs?eval_passed=false")
    assert eval_failed.status_code == 200
    eval_failed_ids = {item["id"] for item in eval_failed.json()}
    assert str(failing.id) in eval_failed_ids
    assert str(passing.id) not in eval_failed_ids

    guardrail_only = client.get("/api/runs?guardrail_blocked=true")
    assert guardrail_only.status_code == 200
    guardrail_ids = {item["id"] for item in guardrail_only.json()}
    assert str(blocked.id) in guardrail_ids
    assert str(passing.id) not in guardrail_ids

    has_eval = client.get("/api/runs?has_eval=true")
    assert has_eval.status_code == 200
    has_eval_ids = {item["id"] for item in has_eval.json()}
    assert str(passing.id) in has_eval_ids
    assert str(failing.id) in has_eval_ids
    assert str(plain.id) not in has_eval_ids


def test_quality_webhook_guardrail_blocked():
    workflow = SimpleNamespace(id=uuid4(), name="Webhook Flow", webhook_url="https://example.com/hook")
    run = SimpleNamespace(
        id=uuid4(),
        status="failed",
        final_output="blocked",
        metrics_json={"guardrail_blocked": True, "failed_guardrails": ["g1"]},
    )

    with patch("app.services.quality_alerts.schedule_task") as mock_task:
        quality_webhook_for_run(None, run, workflow)
        mock_task.assert_called_once()


def test_quality_webhook_eval_failed():
    workflow = SimpleNamespace(id=uuid4(), name="Webhook Flow", webhook_url="https://example.com/hook")
    run = SimpleNamespace(
        id=uuid4(),
        status="completed",
        final_output="done",
        metrics_json={
            "eval_passed": False,
            "eval_aggregate": 2.5,
            "eval_scores": [{"aggregate_score": 2.5}],
        },
    )

    with patch("app.services.quality_alerts.schedule_task") as mock_task:
        quality_webhook_for_run(None, run, workflow)
        mock_task.assert_called_once()


def test_quality_webhook_skips_without_url():
    workflow = SimpleNamespace(id=uuid4(), name="No Hook", webhook_url=None)
    run = SimpleNamespace(
        id=uuid4(),
        status="failed",
        final_output="blocked",
        metrics_json={"guardrail_blocked": True},
    )

    with patch("app.services.quality_alerts.schedule_task") as mock_task:
        quality_webhook_for_run(None, run, workflow)
        mock_task.assert_not_called()