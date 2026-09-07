"""Guards for the run-concurrency gate: orphaned pending/running runs must not
permanently exhaust ``max_concurrent_runs`` (see services/run_concurrency).
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

from app.db import models
from app.db.database import SessionLocal
from app.services.run_concurrency import (
    STALE_RUN_MESSAGE,
    count_active_runs,
    sweep_stale_runs,
)


def _seed_run(status: str, *, age_seconds: int) -> models.WorkflowRun:
    """Create a run whose created_at is `age_seconds` in the past (naive UTC to
    match the func.now()-populated column)."""
    db = SessionLocal()
    try:
        workflow = models.Workflow(id=uuid4(), user_id=uuid4(), name="Concurrency Test")
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

        run = models.WorkflowRun(
            id=uuid4(),
            workflow_version_id=version.id,
            status=status,
            input_text="test",
            created_at=_utcnow_naive() - timedelta(seconds=age_seconds),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()


def test_count_active_runs_excludes_stale_orphans():
    """A pending run older than the staleness window must not count toward the
    gate — otherwise a single zombie permanently blocks new runs with 429."""
    fresh = _seed_run("pending", age_seconds=5)
    stale = _seed_run("pending", age_seconds=24 * 3600)  # a day old

    db = SessionLocal()
    try:
        active = count_active_runs(db)
        ids = {
            r.id
            for r in db.query(models.WorkflowRun)
            .filter(models.WorkflowRun.status.in_(("pending", "running")))
            .all()
        }
        # The fresh run is present and counted; the stale one is present but not.
        assert fresh.id in ids and stale.id in ids
        assert active >= 1  # at least the fresh run
        # Sanity: excluding-stale count is strictly below the raw pending count.
        raw = (
            db.query(models.WorkflowRun)
            .filter(
                models.WorkflowRun.status.in_(("pending", "running")),
                models.WorkflowRun.id.in_([fresh.id, stale.id]),
            )
            .count()
        )
        assert raw == 2
        # Only the fresh one of our two seeds is inside the window.
        windowed = (
            db.query(models.WorkflowRun)
            .filter(
                models.WorkflowRun.status.in_(("pending", "running")),
                models.WorkflowRun.id.in_([fresh.id, stale.id]),
                models.WorkflowRun.created_at
                >= _utcnow_naive() - timedelta(seconds=900),
            )
            .count()
        )
        assert windowed == 1
    finally:
        db.close()


def test_sweep_stale_runs_reaps_orphans_only():
    """sweep_stale_runs marks stale pending/running rows failed and leaves
    fresh ones untouched."""
    fresh = _seed_run("running", age_seconds=5)
    stale = _seed_run("pending", age_seconds=24 * 3600)

    db = SessionLocal()
    try:
        swept = sweep_stale_runs(db)
        assert swept >= 1

        stale_after = db.get(models.WorkflowRun, stale.id)
        fresh_after = db.get(models.WorkflowRun, fresh.id)
        assert stale_after.status == "failed"
        assert stale_after.final_output == STALE_RUN_MESSAGE
        assert stale_after.completed_at is not None
        # Fresh run is still in-flight.
        assert fresh_after.status == "running"
    finally:
        db.close()
