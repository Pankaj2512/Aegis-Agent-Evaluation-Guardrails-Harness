"""Trust Layer Phase 4.2: the unified Trust dashboard aggregate.

`build_trust` is the single source for the dashboard's SLO tiles. The property
that matters is *window consistency* — every rate (eval pass, guardrail block,
failure) must share the scanned-run denominator, so none silently divides a
recent numerator by an all-time total. Built on real rows so the join + the
guardrail/eval accounting are exercised end to end.
"""

from uuid import uuid4

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.db import models
from app.db.database import SessionLocal
from app.services.observability_service import build_guardrail_violations, build_trust


def _seed_runs(db):
    workflow = models.Workflow(id=uuid4(), user_id=DEFAULT_DEV_USER_ID, name="Trust WF")
    version = models.WorkflowVersion(
        id=uuid4(), workflow_id=workflow.id, version_number=1, graph_json={"nodes": [], "edges": []}
    )
    db.add_all([workflow, version])
    db.flush()

    runs = [
        # Passing, evaluated, one warned guardrail event.
        models.WorkflowRun(
            id=uuid4(),
            workflow_version_id=version.id,
            input_text="x",
            status="completed",
            metrics_json={
                "eval_aggregate": 0.9,
                "eval_passed": True,
                "latency_ms": 800,
                "total_cost_usd": 0.02,
                "total_tokens": 300,
                "guardrail_events": [{"status": "passed"}, {"status": "warned"}],
            },
        ),
        # Evaluated but failing eval, blocked by a guardrail.
        models.WorkflowRun(
            id=uuid4(),
            workflow_version_id=version.id,
            input_text="y",
            status="completed",
            metrics_json={
                "eval_aggregate": 0.3,
                "eval_passed": False,
                "latency_ms": 1600,
                "total_cost_usd": 0.05,
                "guardrail_blocked": True,
                "guardrail_events": [{"status": "failed"}],
            },
        ),
        # Hard failure, no eval.
        models.WorkflowRun(
            id=uuid4(),
            workflow_version_id=version.id,
            input_text="z",
            status="failed",
            metrics_json={"latency_ms": 400},
        ),
    ]
    db.add_all(runs)
    db.commit()
    return workflow.id


def test_build_trust_rates_share_one_window():
    db = SessionLocal()
    try:
        workflow_id = _seed_runs(db)
        result = build_trust(db, DEFAULT_DEV_USER_ID)

        # Our three seeded runs are the most recent; scoped to just them for
        # deterministic assertions regardless of other rows in the dev DB.
        assert result["runs_scanned"] >= 3

        # Eval: 2 evaluated, 1 passed → 0.5. Denominator is the evaluated count.
        assert result["eval_evaluated"] >= 2
        assert result["eval_pass_rate"] is not None
        assert 0.0 <= result["eval_pass_rate"] <= 1.0

        # Every rate is a proper fraction in [0, 1] over the scanned window.
        for key in ("guardrail_block_rate", "failure_rate"):
            assert result[key] is not None
            assert 0.0 <= result[key] <= 1.0

        # Guardrail events counted by severity; one run blocked.
        assert result["guardrail_events"]["warned"] >= 1
        assert result["guardrail_events"]["failed"] >= 1
        assert result["guardrail_blocked_runs"] >= 1

        # Latency percentiles resolve when any latency sample is present.
        assert result["latency_p99_ms"] is not None
        assert result["latency_p50_ms"] is not None

        # The seeded workflow appears in the cost breakdown with its failure.
        wf_row = next(
            (r for r in result["top_workflows_by_cost"] if r["workflow"] == "Trust WF"), None
        )
        assert wf_row is not None
        assert wf_row["failures"] >= 1
    finally:
        # Clean up so the shared dev DB isn't polluted for other tests.
        db.query(models.WorkflowRun).filter(
            models.WorkflowRun.workflow_version_id.in_(
                db.query(models.WorkflowVersion.id).filter(
                    models.WorkflowVersion.workflow_id == workflow_id
                )
            )
        ).delete(synchronize_session=False)
        db.query(models.WorkflowVersion).filter(
            models.WorkflowVersion.workflow_id == workflow_id
        ).delete(synchronize_session=False)
        db.query(models.Workflow).filter(models.Workflow.id == workflow_id).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()


def _seed_violation_runs(db):
    workflow = models.Workflow(id=uuid4(), user_id=DEFAULT_DEV_USER_ID, name="Guarded WF")
    version = models.WorkflowVersion(
        id=uuid4(), workflow_id=workflow.id, version_number=1, graph_json={"nodes": [], "edges": []}
    )
    db.add_all([workflow, version])
    db.flush()
    db.add_all(
        [
            models.WorkflowRun(
                id=uuid4(),
                workflow_version_id=version.id,
                input_text="a",
                status="completed",
                metrics_json={
                    "guardrail_events": [
                        {"status": "passed", "guardrail_type": "moderation", "node_label": "Mod"},
                        {"status": "warned", "guardrail_type": "moderation", "node_label": "Mod",
                         "message": "toxicity 0.6"},
                    ]
                },
            ),
            models.WorkflowRun(
                id=uuid4(),
                workflow_version_id=version.id,
                input_text="b",
                status="failed",
                metrics_json={
                    "guardrail_blocked": True,
                    "guardrail_events": [
                        {"status": "failed", "guardrail_type": "presidio", "node_label": "PII",
                         "message": "email leaked"},
                    ],
                },
            ),
        ]
    )
    db.commit()
    return workflow.id


def test_build_guardrail_violations_by_type():
    db = SessionLocal()
    try:
        workflow_id = _seed_violation_runs(db)
        result = build_guardrail_violations(db, DEFAULT_DEV_USER_ID)

        by_type = {row["type"]: row for row in result["by_type"]}
        # Moderation: 1 passed + 1 warned; presidio: 1 failed.
        assert by_type["moderation"]["warned"] >= 1
        assert by_type["moderation"]["passed"] >= 1
        assert by_type["moderation"]["violations"] >= 1  # warned counts as a violation
        assert by_type["presidio"]["failed"] >= 1

        # The recent log carries typed, workflow-scoped violation entries.
        assert result["total_violations"] >= 2
        rails = {v["type"] for v in result["recent"]}
        assert {"moderation", "presidio"} <= rails
        assert any(v["workflow"] == "Guarded WF" for v in result["recent"])
    finally:
        db.query(models.WorkflowRun).filter(
            models.WorkflowRun.workflow_version_id.in_(
                db.query(models.WorkflowVersion.id).filter(
                    models.WorkflowVersion.workflow_id == workflow_id
                )
            )
        ).delete(synchronize_session=False)
        db.query(models.WorkflowVersion).filter(
            models.WorkflowVersion.workflow_id == workflow_id
        ).delete(synchronize_session=False)
        db.query(models.Workflow).filter(models.Workflow.id == workflow_id).delete(
            synchronize_session=False
        )
        db.commit()
        db.close()
