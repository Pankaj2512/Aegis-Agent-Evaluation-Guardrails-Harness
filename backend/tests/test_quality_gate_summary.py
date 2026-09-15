"""Unit tests for Aegis Quality Gate markdown summary generation and API endpoint."""

from datetime import datetime, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.db import models
from app.db.database import SessionLocal
from app.main import app
from app.schemas.quality_gate import (
    QualityCheckItem,
    QualityCheckStatus,
    QualityGateReport,
)
from app.services.quality_gate import format_quality_gate_markdown_summary

client = TestClient(app)


def test_format_quality_gate_markdown_passed():
    """Verify markdown output when all quality gate checks pass."""
    wf_id = uuid4()
    ver_id = uuid4()
    report = QualityGateReport(
        workflow_id=wf_id,
        version_id=ver_id,
        version_number=2,
        passed=True,
        can_publish=True,
        gate_enabled=True,
        summary="Quality gate PASSED (3 checks evaluated, 0 warning(s)). Version ready for production.",
        checks=[
            QualityCheckItem(
                check_id="min_eval_score",
                name="Minimum Eval Score",
                status=QualityCheckStatus.PASSED,
                metric_value=4.8,
                threshold_value=4.0,
                details="Average score 4.80 meets threshold >= 4.00.",
            ),
            QualityCheckItem(
                check_id="guardrail_block_rate",
                name="Guardrail Block Rate",
                status=QualityCheckStatus.PASSED,
                metric_value=0.0,
                threshold_value=0.05,
                details="Block rate 0.0% is within threshold <= 5.0%.",
            ),
        ],
        blockers=[],
        warnings=[],
        candidate_metrics={
            "total_runs": 25,
            "avg_eval_score": 4.8,
            "eval_pass_rate": 0.96,
            "guardrail_block_rate": 0.0,
            "p95_latency_ms": 280.0,
        },
    )

    md = format_quality_gate_markdown_summary(report)

    assert "# 🛡️ Aegis Quality Gate Report" in md
    assert "Quality%20Gate-PASSED-brightgreen" in md
    assert "Can Publish:** ✅ Yes" in md
    assert str(wf_id) in md
    assert "v2" in md
    assert "Minimum Eval Score" in md
    assert "Guardrail Block Rate" in md
    assert "✅ Pass" in md
    assert "4.80 / 5.0" in md
    assert "96.0%" in md
    assert "280 ms" in md
    assert "### ❌ Blocking Issues" not in md


def test_format_quality_gate_markdown_failed_with_remediation():
    """Verify markdown output includes blockers, warnings, and remediations when checks fail."""
    wf_id = uuid4()
    ver_id = uuid4()
    report = QualityGateReport(
        workflow_id=wf_id,
        version_id=ver_id,
        version_number=3,
        passed=False,
        can_publish=False,
        gate_enabled=True,
        summary="Quality gate FAILED (1 blocking violation(s) detected).",
        checks=[
            QualityCheckItem(
                check_id="min_eval_score",
                name="Minimum Eval Score",
                status=QualityCheckStatus.FAILED,
                metric_value=2.8,
                threshold_value=3.5,
                details="Average score 2.80 is below threshold >= 3.50.",
                remediation="Refine system prompt and examples to boost accuracy.",
            ),
        ],
        blockers=["Average evaluation score 2.80 is below required threshold 3.50."],
        warnings=["Low benchmark run count: only 2 evaluated runs."],
        candidate_metrics={
            "total_runs": 2,
            "avg_eval_score": 2.8,
            "eval_pass_rate": 0.5,
            "guardrail_block_rate": 0.0,
            "p95_latency_ms": 320.0,
        },
    )

    md = format_quality_gate_markdown_summary(report)

    assert "Quality%20Gate-FAILED-red" in md
    assert "Can Publish:** ❌ No" in md
    assert "### ❌ Blocking Issues" in md
    assert "Average evaluation score 2.80 is below required threshold 3.50." in md
    assert "### ⚠️ Warnings" in md
    assert "Low benchmark run count" in md
    assert "### 🔧 Recommended Actions" in md
    assert "Refine system prompt and examples to boost accuracy." in md
    assert "❌ Fail" in md


def test_api_quality_gate_summary_endpoint():
    """Test the GET /api/workflows/{workflow_id}/versions/{version_id}/quality-gate/summary HTTP endpoint."""
    db = SessionLocal()
    try:
        wf = models.Workflow(
            name="Markdown Summary API Workflow",
            user_id=DEFAULT_DEV_USER_ID,
            description="Testing markdown summary endpoint",
        )
        db.add(wf)
        db.flush()

        ver = models.WorkflowVersion(
            workflow_id=wf.id,
            version_number=1,
            graph_json={"nodes": [], "edges": []},
        )
        db.add(ver)
        db.commit()

        response = client.get(f"/api/workflows/{wf.id}/versions/{ver.id}/quality-gate/summary")
        assert response.status_code == 200
        assert "text/markdown" in response.headers.get("content-type", "")
        content = response.text
        assert "# 🛡️ Aegis Quality Gate Report" in content
        assert str(wf.id) in content
        assert "v1" in content
    finally:
        db.close()


def test_api_quality_gate_summary_not_found():
    """Test that nonexistent workflow/version returns 404."""
    fake_wf_id = uuid4()
    fake_ver_id = uuid4()
    response = client.get(f"/api/workflows/{fake_wf_id}/versions/{fake_ver_id}/quality-gate/summary")
    assert response.status_code == 404
