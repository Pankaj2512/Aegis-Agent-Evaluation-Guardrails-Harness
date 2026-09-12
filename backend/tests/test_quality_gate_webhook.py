"""Tests for Quality Gate Webhook notification dispatch."""

from unittest.mock import patch
from uuid import uuid4

from app.db import models
from app.schemas.quality_gate import QualityGateReport
from app.services.quality_alerts import schedule_quality_gate_webhook


def test_schedule_quality_gate_webhook_success() -> None:
    wf_id = uuid4()
    v_id = uuid4()
    workflow = models.Workflow(id=wf_id, name="Test Agent", webhook_url="https://example.com/webhook")
    version = models.WorkflowVersion(id=v_id, workflow_id=wf_id, version_number=2)

    report = QualityGateReport(
        workflow_id=wf_id,
        version_id=v_id,
        version_number=2,
        passed=True,
        can_publish=True,
        gate_enabled=True,
        summary="Quality gate passed successfully.",
        checks=[],
        blockers=[],
        warnings=[],
        candidate_metrics={"avg_eval_score": 0.95},
    )

    with patch("app.services.quality_alerts.schedule_task") as mock_schedule:
        schedule_quality_gate_webhook(workflow, version, report, action="publish_attempt")
        assert mock_schedule.called
        # Verify call arguments
        coro = mock_schedule.call_args[0][0]
        assert coro is not None


def test_schedule_quality_gate_webhook_no_url() -> None:
    wf_id = uuid4()
    v_id = uuid4()
    workflow = models.Workflow(id=wf_id, name="Test Agent", webhook_url=None)
    version = models.WorkflowVersion(id=v_id, workflow_id=wf_id, version_number=2)

    report = QualityGateReport(
        workflow_id=wf_id,
        version_id=v_id,
        version_number=2,
        passed=False,
        can_publish=False,
        gate_enabled=True,
        summary="Quality gate failed.",
        checks=[],
        blockers=["Score below threshold"],
        warnings=[],
    )

    with patch("app.services.quality_alerts.schedule_task") as mock_schedule:
        schedule_quality_gate_webhook(workflow, version, report)
        assert not mock_schedule.called
