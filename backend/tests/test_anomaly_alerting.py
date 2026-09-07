"""Anomaly / percentile alerting (alerts.py extension).

Covers the two additions: latency percentile metrics and baseline-relative
(anomaly) comparison. Uses real rows with controlled ``created_at`` so the
current vs trailing-baseline windows are exercised; asserts on the pure
``_rule_breach`` decision so there are no webhook/commit side effects.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.db import models
from app.db.database import SessionLocal
from app.services.alerts import _metric_value, _rule_breach


def _mk_workflow(db):
    wf = models.Workflow(id=uuid4(), user_id=DEFAULT_DEV_USER_ID, name="Alert WF")
    version = models.WorkflowVersion(
        id=uuid4(), workflow_id=wf.id, version_number=1, graph_json={"nodes": [], "edges": []}
    )
    db.add_all([wf, version])
    db.flush()
    return wf, version


def _run(version, *, status="completed", minutes_ago=1, metrics=None):
    created = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).replace(tzinfo=None)
    return models.WorkflowRun(
        id=uuid4(),
        workflow_version_id=version.id,
        input_text="x",
        status=status,
        created_at=created,
        metrics_json=metrics or {},
    )


def _cleanup(db, workflow_id):
    version_ids = db.query(models.WorkflowVersion.id).filter(
        models.WorkflowVersion.workflow_id == workflow_id
    )
    db.query(models.WorkflowRun).filter(
        models.WorkflowRun.workflow_version_id.in_(version_ids)
    ).delete(synchronize_session=False)
    db.query(models.WorkflowVersion).filter(
        models.WorkflowVersion.workflow_id == workflow_id
    ).delete(synchronize_session=False)
    db.query(models.Workflow).filter(models.Workflow.id == workflow_id).delete(
        synchronize_session=False
    )
    db.commit()


def test_latency_p99_metric():
    db = SessionLocal()
    try:
        wf, version = _mk_workflow(db)
        for ms in (100, 200, 300, 400, 500, 600, 700, 800, 900, 5000):
            db.add(_run(version, minutes_ago=2, metrics={"latency_ms": ms}))
        db.commit()

        rule = models.AlertRule(
            id=uuid4(), user_id=DEFAULT_DEV_USER_ID, workflow_id=wf.id,
            metric="latency_p99", operator="gt", threshold=2000, window_minutes=60,
        )
        # p99 of the 10 samples picks the top bucket — the 5000ms outlier.
        assert _metric_value(db, rule) == 5000
        breach = _rule_breach(db, rule)
        assert breach is not None and breach[0] == 5000
    finally:
        _cleanup(db, wf.id)
        db.close()


def test_baseline_anomaly_fires_on_ratio_spike():
    db = SessionLocal()
    try:
        wf, version = _mk_workflow(db)
        # Current 60m window: 3 of 3 failed → failure_rate 1.0.
        for _ in range(3):
            db.add(_run(version, status="failed", minutes_ago=5))
        # Older (within the 360m baseline, outside the 60m current): 7 clean runs.
        for _ in range(7):
            db.add(_run(version, status="completed", minutes_ago=120))
        db.commit()

        rule = models.AlertRule(
            id=uuid4(), user_id=DEFAULT_DEV_USER_ID, workflow_id=wf.id,
            metric="failure_rate", operator="gt", threshold=2.0,
            window_minutes=60, comparison="baseline", baseline_window_minutes=360,
        )
        # current = 3/3 = 1.0; baseline = 3/10 = 0.3; ratio ≈ 3.33 > 2.0 → fires.
        breach = _rule_breach(db, rule)
        assert breach is not None
        value, message, comparison = breach
        assert comparison == "baseline"
        assert "Anomaly" in message and "baseline" in message

        # The same numbers under absolute comparison do NOT breach a 2.0 threshold
        # (failure_rate maxes at 1.0), proving the modes differ.
        rule.comparison = "absolute"
        assert _rule_breach(db, rule) is None
    finally:
        _cleanup(db, wf.id)
        db.close()


def test_baseline_needs_a_nonzero_baseline():
    db = SessionLocal()
    try:
        wf, version = _mk_workflow(db)
        # Only recent runs, nothing older → baseline == current, ratio 1.0, no fire.
        for _ in range(2):
            db.add(_run(version, status="failed", minutes_ago=5))
        db.commit()
        rule = models.AlertRule(
            id=uuid4(), user_id=DEFAULT_DEV_USER_ID, workflow_id=wf.id,
            metric="failure_rate", operator="gt", threshold=2.0,
            window_minutes=60, comparison="baseline", baseline_window_minutes=360,
        )
        # baseline == current (1.0), ratio 1.0, not > 2.0.
        assert _rule_breach(db, rule) is None
    finally:
        _cleanup(db, wf.id)
        db.close()
