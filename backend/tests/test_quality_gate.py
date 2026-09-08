"""Comprehensive tests for Aegis Quality Gate verification and pre-publish enforcement."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.db import models
from app.db.database import SessionLocal
from app.main import app
from app.schemas.quality_gate import QualityCheckStatus, QualityGateConfig
from app.services.quality_gate import (
    compute_version_quality_metrics,
    evaluate_quality_gate,
    extract_quality_gate_config,
)

client = TestClient(app)


def _create_test_workflow_and_version(db, graph_json=None, published=False):
    user_id = DEFAULT_DEV_USER_ID
    wf = models.Workflow(
        name="Quality Gate Test Workflow",
        user_id=user_id,
        description="Testing pre-publish gating",
    )
    db.add(wf)
    db.flush()

    ver = models.WorkflowVersion(
        workflow_id=wf.id,
        version_number=1,
        graph_json=graph_json or {"nodes": [], "edges": []},
    )
    db.add(ver)
    db.flush()

    if published:
        wf.published_version_id = ver.id
        db.flush()

    db.commit()
    return wf, ver


def _create_mock_run(db, version_id, *, eval_aggregate=None, eval_passed=None, guardrail_blocked=False, duration_ms=100.0, status="completed"):
    metrics = {
        "eval_aggregate": eval_aggregate,
        "eval_passed": eval_passed,
        "guardrail_blocked": guardrail_blocked,
        "duration_ms": duration_ms,
    }
    run = models.WorkflowRun(
        id=uuid4(),
        workflow_version_id=version_id,
        status="blocked" if guardrail_blocked else status,
        input_text="Sample test input prompt",
        final_output="Sample test output answer",
        metrics_json=metrics,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    return run



def test_compute_version_quality_metrics_empty():
    res = compute_version_quality_metrics([])
    assert res["total_runs"] == 0
    assert res["evaluated_runs"] == 0
    assert res["avg_eval_score"] is None
    assert res["eval_pass_rate"] is None
    assert res["guardrail_block_rate"] == 0.0
    assert res["p95_latency_ms"] is None


def test_compute_version_quality_metrics_aggregates():
    db = SessionLocal()
    try:
        wf, ver = _create_test_workflow_and_version(db)
        r1 = _create_mock_run(db, ver.id, eval_aggregate=4.5, eval_passed=True, duration_ms=150.0)
        r2 = _create_mock_run(db, ver.id, eval_aggregate=3.5, eval_passed=False, duration_ms=250.0)
        r3 = _create_mock_run(db, ver.id, eval_aggregate=None, guardrail_blocked=True, duration_ms=50.0)

        runs = [r1, r2, r3]
        metrics = compute_version_quality_metrics(runs)
        assert metrics["total_runs"] == 3
        assert metrics["evaluated_runs"] == 2
        assert metrics["eval_passed_count"] == 1
        assert metrics["eval_failed_count"] == 1
        assert metrics["avg_eval_score"] == 4.0
        assert metrics["eval_pass_rate"] == 0.5
        assert metrics["guardrail_blocked_runs"] == 1
        assert metrics["guardrail_block_rate"] == round(1 / 3, 4)
        assert metrics["p95_latency_ms"] is not None
    finally:
        db.close()


def test_evaluate_quality_gate_disabled():
    db = SessionLocal()
    try:
        wf, ver = _create_test_workflow_and_version(
            db, graph_json={"quality_gate": {"enabled": False}}
        )
        report = evaluate_quality_gate(db, wf, ver)
        assert report.passed is True
        assert report.can_publish is True
        assert report.gate_enabled is False
        assert len(report.blockers) == 0
    finally:
        db.close()


def test_evaluate_quality_gate_passing_version():
    db = SessionLocal()
    try:
        wf, ver = _create_test_workflow_and_version(
            db,
            graph_json={
                "quality_gate": {
                    "enabled": True,
                    "min_eval_score": 3.0,
                    "min_pass_rate": 0.70,
                    "max_guardrail_block_rate": 0.20,
                    "max_p95_latency_ms": 1000.0,
                }
            },
        )
        # Healthy runs
        _create_mock_run(db, ver.id, eval_aggregate=4.2, eval_passed=True, duration_ms=100.0)
        _create_mock_run(db, ver.id, eval_aggregate=4.0, eval_passed=True, duration_ms=120.0)

        report = evaluate_quality_gate(db, wf, ver)
        assert report.passed is True
        assert report.can_publish is True
        assert len(report.blockers) == 0
        assert any(c.check_id == "min_eval_score" and c.status == QualityCheckStatus.PASSED for c in report.checks)
        assert any(c.check_id == "min_pass_rate" and c.status == QualityCheckStatus.PASSED for c in report.checks)
    finally:
        db.close()


def test_evaluate_quality_gate_failing_eval_threshold():
    db = SessionLocal()
    try:
        wf, ver = _create_test_workflow_and_version(
            db,
            graph_json={"quality_gate": {"enabled": True, "min_eval_score": 4.0}},
        )
        # Poor runs
        _create_mock_run(db, ver.id, eval_aggregate=2.5, eval_passed=False)
        _create_mock_run(db, ver.id, eval_aggregate=3.0, eval_passed=False)

        report = evaluate_quality_gate(db, wf, ver)
        assert report.passed is False
        assert report.can_publish is False
        assert len(report.blockers) >= 1
        assert any(c.check_id == "min_eval_score" and c.status == QualityCheckStatus.FAILED for c in report.checks)
    finally:
        db.close()


def test_evaluate_quality_gate_guardrail_block_rate_exceeded():
    db = SessionLocal()
    try:
        wf, ver = _create_test_workflow_and_version(
            db,
            graph_json={"quality_gate": {"enabled": True, "max_guardrail_block_rate": 0.10}},
        )
        # 2 blocked out of 3 runs -> block rate 66% > 10%
        _create_mock_run(db, ver.id, guardrail_blocked=True)
        _create_mock_run(db, ver.id, guardrail_blocked=True)
        _create_mock_run(db, ver.id, guardrail_blocked=False, eval_aggregate=4.5, eval_passed=True)

        report = evaluate_quality_gate(db, wf, ver)
        assert report.passed is False
        assert any(c.check_id == "guardrail_block_rate" and c.status == QualityCheckStatus.FAILED for c in report.checks)
    finally:
        db.close()


def test_evaluate_quality_gate_regression_detected():
    db = SessionLocal()
    try:
        wf, ver_base = _create_test_workflow_and_version(db, published=True)
        # Baseline had high score (4.8)
        _create_mock_run(db, ver_base.id, eval_aggregate=4.8, eval_passed=True)

        # Candidate version v2
        ver_cand = models.WorkflowVersion(
            workflow_id=wf.id,
            version_number=2,
            graph_json={"quality_gate": {"enabled": True, "block_on_regression": True, "regression_tolerance": 0.20}},
        )
        db.add(ver_cand)
        db.commit()

        # Candidate has much lower score (3.5) -> delta -1.3 exceeds tolerance 0.20
        _create_mock_run(db, ver_cand.id, eval_aggregate=3.5, eval_passed=True)

        report = evaluate_quality_gate(db, wf, ver_cand)
        assert report.passed is False
        assert any(c.check_id == "eval_regression" and c.status == QualityCheckStatus.FAILED for c in report.checks)
        assert any("Regression detected" in b for b in report.blockers)
    finally:
        db.close()


def test_evaluate_quality_gate_required_eval_runs():
    db = SessionLocal()
    try:
        wf, ver = _create_test_workflow_and_version(
            db,
            graph_json={"quality_gate": {"enabled": True, "require_eval_runs": True, "min_runs_evaluated": 2}},
        )
        # Only 1 evaluated run provided
        _create_mock_run(db, ver.id, eval_aggregate=4.5, eval_passed=True)

        report = evaluate_quality_gate(db, wf, ver)
        assert report.passed is False
        assert any(c.check_id == "required_eval_runs" and c.status == QualityCheckStatus.FAILED for c in report.checks)
    finally:
        db.close()


def test_api_quality_gate_inspect_endpoint():
    db = SessionLocal()
    try:
        wf, ver = _create_test_workflow_and_version(db)
        _create_mock_run(db, ver.id, eval_aggregate=4.0, eval_passed=True)

        resp = client.get(f"/api/workflows/{wf.id}/versions/{ver.id}/quality-gate")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["workflow_id"] == str(wf.id)
        assert data["version_id"] == str(ver.id)
        assert "can_publish" in data
        assert "checks" in data
        assert "candidate_metrics" in data
    finally:
        db.close()


def test_api_publish_enforces_quality_gate_and_allows_force():
    db = SessionLocal()
    try:
        wf, ver = _create_test_workflow_and_version(
            db,
            graph_json={"quality_gate": {"enabled": True, "min_eval_score": 4.5}},
        )
        # Subpar run (3.0 < 4.5)
        _create_mock_run(db, ver.id, eval_aggregate=3.0, eval_passed=False)

        # 1. Normal publish should be rejected (422)
        resp = client.post(
            f"/api/workflows/{wf.id}/publish",
            json={"version_id": str(ver.id)},
        )
        assert resp.status_code == 422, resp.text
        err = resp.json()
        assert "quality_gate_failed" in str(err)

        # 2. Force publish should bypass gate
        resp_force = client.post(
            f"/api/workflows/{wf.id}/publish",
            json={"version_id": str(ver.id), "force": True, "override_reason": "Emergency hotfix"},
        )
        assert resp_force.status_code == 200, resp_force.text
        data = resp_force.json()
        assert data["published_version_id"] == str(ver.id)
        assert data["bypassed"] is True
    finally:
        db.close()
