"""Quality Gate evaluation and pre-publish verification service.

Analyzes candidate workflow versions against configured quality thresholds:
- Evaluation score aggregates and pass rates
- Guardrail violation / block rates
- Performance latency SLA (p95)
- Regression comparison against currently published baseline version
- Pre-deployment test/benchmark run completeness
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import models
from app.schemas.quality_gate import (
    QualityCheckItem,
    QualityCheckStatus,
    QualityGateConfig,
    QualityGateReport,
)

logger = logging.getLogger("aegis.quality_gate")


def extract_quality_gate_config(
    workflow: models.Workflow,
    version: models.WorkflowVersion,
) -> QualityGateConfig:
    """Extract quality gate configuration from version graph_json or workflow metadata."""
    graph_json = version.graph_json or {}
    raw_cfg = graph_json.get("quality_gate")

    if not raw_cfg and workflow.budget_json:
        raw_cfg = workflow.budget_json.get("quality_gate")

    if isinstance(raw_cfg, dict):
        try:
            return QualityGateConfig(**raw_cfg)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Invalid quality gate config in workflow %s: %s", workflow.id, exc)

    return QualityGateConfig()


def compute_version_quality_metrics(runs: list[models.WorkflowRun]) -> dict[str, Any]:
    """Compute aggregate quality, guardrail, and latency metrics for a set of runs."""
    total_runs = len(runs)
    evaluated_runs = 0
    eval_passed_count = 0
    eval_failed_count = 0
    eval_scores: list[float] = []
    guardrail_blocked_runs = 0
    durations_ms: list[float] = []

    for run in runs:
        metrics = run.metrics_json or {}

        # Eval metrics
        aggregate = metrics.get("eval_aggregate")
        if aggregate is not None:
            try:
                score_val = float(aggregate)
                eval_scores.append(score_val)
                evaluated_runs += 1
                passed = metrics.get("eval_passed")
                if passed is True:
                    eval_passed_count += 1
                elif passed is False:
                    eval_failed_count += 1
            except (ValueError, TypeError):
                pass

        # Guardrail metrics
        if metrics.get("guardrail_blocked") is True or run.status == "blocked":
            guardrail_blocked_runs += 1

        # Latency / duration metrics
        duration = metrics.get("duration_ms")
        if duration is not None:
            try:
                durations_ms.append(float(duration))
            except (ValueError, TypeError):
                pass
        elif run.started_at and run.completed_at:
            delta_ms = (run.completed_at - run.started_at).total_seconds() * 1000.0
            if delta_ms >= 0:
                durations_ms.append(delta_ms)

    avg_eval_score = round(sum(eval_scores) / len(eval_scores), 2) if eval_scores else None
    eval_pass_rate = round(eval_passed_count / evaluated_runs, 4) if evaluated_runs > 0 else None
    guardrail_block_rate = round(guardrail_blocked_runs / total_runs, 4) if total_runs > 0 else 0.0

    p95_latency_ms: float | None = None
    if durations_ms:
        sorted_durations = sorted(durations_ms)
        p95_idx = int(len(sorted_durations) * 0.95)
        p95_latency_ms = round(sorted_durations[min(p95_idx, len(sorted_durations) - 1)], 1)

    return {
        "total_runs": total_runs,
        "evaluated_runs": evaluated_runs,
        "eval_passed_count": eval_passed_count,
        "eval_failed_count": eval_failed_count,
        "avg_eval_score": avg_eval_score,
        "eval_pass_rate": eval_pass_rate,
        "guardrail_blocked_runs": guardrail_blocked_runs,
        "guardrail_block_rate": guardrail_block_rate,
        "p95_latency_ms": p95_latency_ms,
        "avg_latency_ms": round(sum(durations_ms) / len(durations_ms), 1) if durations_ms else None,
    }


def evaluate_quality_gate(
    db: Session,
    workflow: models.Workflow,
    candidate_version: models.WorkflowVersion,
    policy_override: QualityGateConfig | None = None,
    run_limit: int = 50,
) -> QualityGateReport:
    """Evaluate candidate workflow version readiness against active quality gate rules."""
    policy = policy_override or extract_quality_gate_config(workflow, candidate_version)

    # Fetch candidate runs
    candidate_runs = (
        db.query(models.WorkflowRun)
        .filter(models.WorkflowRun.version_id == candidate_version.id)
        .order_by(models.WorkflowRun.created_at.desc())
        .limit(run_limit)
        .all()
    )
    cand_metrics = compute_version_quality_metrics(candidate_runs)

    # Fetch baseline runs if currently published version exists
    baseline_metrics: dict[str, Any] | None = None
    if workflow.published_version_id and workflow.published_version_id != candidate_version.id:
        baseline_runs = (
            db.query(models.WorkflowRun)
            .filter(models.WorkflowRun.version_id == workflow.published_version_id)
            .order_by(models.WorkflowRun.created_at.desc())
            .limit(run_limit)
            .all()
        )
        if baseline_runs:
            baseline_metrics = compute_version_quality_metrics(baseline_runs)

    checks: list[QualityCheckItem] = []
    blockers: list[str] = []
    warnings: list[str] = []

    if not policy.enabled:
        return QualityGateReport(
            workflow_id=workflow.id,
            version_id=candidate_version.id,
            version_number=candidate_version.version_number,
            passed=True,
            can_publish=True,
            gate_enabled=False,
            summary="Quality gate is disabled for this workflow.",
            checks=[],
            blockers=[],
            warnings=[],
            candidate_metrics=cand_metrics,
            baseline_metrics=baseline_metrics,
        )

    # Check 1: Required minimum test/eval runs
    if policy.require_eval_runs:
        evaluated_count = cand_metrics["evaluated_runs"]
        if evaluated_count >= policy.min_runs_evaluated:
            checks.append(
                QualityCheckItem(
                    check_id="required_eval_runs",
                    name="Evaluated Runs Requirement",
                    status=QualityCheckStatus.PASSED,
                    metric_value=float(evaluated_count),
                    threshold_value=float(policy.min_runs_evaluated),
                    details=f"{evaluated_count} test/eval run(s) completed (minimum required: {policy.min_runs_evaluated}).",
                )
            )
        else:
            msg = f"Version requires at least {policy.min_runs_evaluated} evaluated run(s), but only found {evaluated_count}."
            blockers.append(msg)
            checks.append(
                QualityCheckItem(
                    check_id="required_eval_runs",
                    name="Evaluated Runs Requirement",
                    status=QualityCheckStatus.FAILED,
                    metric_value=float(evaluated_count),
                    threshold_value=float(policy.min_runs_evaluated),
                    details=msg,
                    remediation="Execute sample runs or run an evaluation experiment on this version before publishing.",
                )
            )

    # Check 2: Minimum average eval score
    cand_avg_score = cand_metrics["avg_eval_score"]
    if policy.min_eval_score is not None:
        if cand_avg_score is not None:
            passed = cand_avg_score >= policy.min_eval_score
            status = QualityCheckStatus.PASSED if passed else QualityCheckStatus.FAILED
            details = f"Average eval score {cand_avg_score:.2f} (target >= {policy.min_eval_score:.2f})."
            if not passed:
                blockers.append(f"Eval score {cand_avg_score:.2f} is below minimum threshold {policy.min_eval_score:.2f}.")
            checks.append(
                QualityCheckItem(
                    check_id="min_eval_score",
                    name="Minimum Eval Score",
                    status=status,
                    metric_value=cand_avg_score,
                    threshold_value=policy.min_eval_score,
                    details=details,
                    remediation="Tune model prompts, improve retrieval contexts, or update criteria." if not passed else None,
                )
            )
        else:
            checks.append(
                QualityCheckItem(
                    check_id="min_eval_score",
                    name="Minimum Eval Score",
                    status=QualityCheckStatus.SKIPPED,
                    details="No evaluated runs recorded yet for this version.",
                    remediation="Run benchmark tests to evaluate output quality before publishing.",
                )
            )
            warnings.append("No evaluation scores recorded yet for candidate version.")

    # Check 3: Minimum eval pass rate
    cand_pass_rate = cand_metrics["eval_pass_rate"]
    if policy.min_pass_rate is not None:
        if cand_pass_rate is not None:
            passed = cand_pass_rate >= policy.min_pass_rate
            status = QualityCheckStatus.PASSED if passed else QualityCheckStatus.FAILED
            details = f"Eval pass rate {cand_pass_rate * 100:.1f}% (target >= {policy.min_pass_rate * 100:.1f}%)."
            if not passed:
                blockers.append(
                    f"Eval pass rate {cand_pass_rate * 100:.1f}% is below required {policy.min_pass_rate * 100:.1f}%."
                )
            checks.append(
                QualityCheckItem(
                    check_id="min_pass_rate",
                    name="Minimum Pass Rate",
                    status=status,
                    metric_value=cand_pass_rate,
                    threshold_value=policy.min_pass_rate,
                    details=details,
                    remediation="Inspect failing run evals to address quality failures." if not passed else None,
                )
            )
        else:
            checks.append(
                QualityCheckItem(
                    check_id="min_pass_rate",
                    name="Minimum Pass Rate",
                    status=QualityCheckStatus.SKIPPED,
                    details="No eval pass/fail verdicts recorded yet for this version.",
                )
            )

    # Check 4: Maximum guardrail block rate
    cand_block_rate = cand_metrics["guardrail_block_rate"]
    if policy.max_guardrail_block_rate is not None:
        if cand_metrics["total_runs"] > 0:
            passed = cand_block_rate <= policy.max_guardrail_block_rate
            status = QualityCheckStatus.PASSED if passed else QualityCheckStatus.FAILED
            details = f"Guardrail block rate {cand_block_rate * 100:.1f}% (maximum allowed <= {policy.max_guardrail_block_rate * 100:.1f}%)."
            if not passed:
                blockers.append(
                    f"Guardrail block rate {cand_block_rate * 100:.1f}% exceeds limit of {policy.max_guardrail_block_rate * 100:.1f}%."
                )
            checks.append(
                QualityCheckItem(
                    check_id="guardrail_block_rate",
                    name="Guardrail Block Rate",
                    status=status,
                    metric_value=cand_block_rate,
                    threshold_value=policy.max_guardrail_block_rate,
                    details=details,
                    remediation="Review guardrail policies or sanitize outputs to reduce policy violations." if not passed else None,
                )
            )
        else:
            checks.append(
                QualityCheckItem(
                    check_id="guardrail_block_rate",
                    name="Guardrail Block Rate",
                    status=QualityCheckStatus.SKIPPED,
                    details="No runs recorded yet to assess guardrail block rate.",
                )
            )

    # Check 5: Latency SLA (p95)
    cand_p95 = cand_metrics["p95_latency_ms"]
    if policy.max_p95_latency_ms is not None:
        if cand_p95 is not None:
            passed = cand_p95 <= policy.max_p95_latency_ms
            status = QualityCheckStatus.PASSED if passed else QualityCheckStatus.FAILED
            details = f"p95 latency {cand_p95:.0f}ms (target <= {policy.max_p95_latency_ms:.0f}ms)."
            if not passed:
                blockers.append(
                    f"p95 execution duration {cand_p95:.0f}ms exceeds SLA limit of {policy.max_p95_latency_ms:.0f}ms."
                )
            checks.append(
                QualityCheckItem(
                    check_id="latency_sla",
                    name="Latency SLA (p95)",
                    status=status,
                    metric_value=cand_p95,
                    threshold_value=policy.max_p95_latency_ms,
                    details=details,
                    remediation="Optimize node parallelization or simplify model prompts to reduce execution latency." if not passed else None,
                )
            )
        else:
            checks.append(
                QualityCheckItem(
                    check_id="latency_sla",
                    name="Latency SLA (p95)",
                    status=QualityCheckStatus.SKIPPED,
                    details="No duration metrics available for this version.",
                )
            )

    # Check 6: Regression vs baseline published version
    if policy.block_on_regression:
        if baseline_metrics and baseline_metrics.get("avg_eval_score") is not None and cand_avg_score is not None:
            base_score = float(baseline_metrics["avg_eval_score"])
            delta = round(cand_avg_score - base_score, 2)
            passed = delta >= -policy.regression_tolerance
            status = QualityCheckStatus.PASSED if passed else QualityCheckStatus.FAILED
            details = f"Score change vs baseline v{workflow.published_version_id}: {delta:+.2f} (tolerance: -{policy.regression_tolerance:.2f})."
            if not passed:
                blockers.append(
                    f"Regression detected: candidate score {cand_avg_score:.2f} is {abs(delta):.2f} below published baseline {base_score:.2f}."
                )
            checks.append(
                QualityCheckItem(
                    check_id="eval_regression",
                    name="Evaluation Regression Check",
                    status=status,
                    metric_value=delta,
                    threshold_value=-policy.regression_tolerance,
                    details=details,
                    remediation="Investigate performance drop against baseline before promoting." if not passed else None,
                )
            )
        else:
            checks.append(
                QualityCheckItem(
                    check_id="eval_regression",
                    name="Evaluation Regression Check",
                    status=QualityCheckStatus.SKIPPED,
                    details="Baseline published version lacks evaluation benchmarks for comparative check.",
                )
            )

    gate_passed = len(blockers) == 0
    if gate_passed:
        summary = f"Quality gate PASSED ({len(checks)} checks evaluated, {len(warnings)} warning(s)). Version ready for production."
    else:
        summary = f"Quality gate FAILED ({len(blockers)} blocking violation(s) detected)."

    return QualityGateReport(
        workflow_id=workflow.id,
        version_id=candidate_version.id,
        version_number=candidate_version.version_number,
        passed=gate_passed,
        can_publish=gate_passed,
        gate_enabled=True,
        summary=summary,
        checks=checks,
        blockers=blockers,
        warnings=warnings,
        candidate_metrics=cand_metrics,
        baseline_metrics=baseline_metrics,
    )
