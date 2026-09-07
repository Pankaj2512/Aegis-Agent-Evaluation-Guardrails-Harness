from datetime import datetime, timezone
from uuid import uuid4

from app.db import models
from app.db.database import SessionLocal
from app.services.startup import STALE_JOB_MESSAGE, STALE_RUN_MESSAGE, recover_stale_jobs, recover_stale_runs


def _seed_run(status: str) -> models.WorkflowRun:
    db = SessionLocal()
    try:
        workflow = models.Workflow(
            id=uuid4(),
            user_id=uuid4(),
            name="Stale Run Test",
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

        run = models.WorkflowRun(
            id=uuid4(),
            workflow_version_id=version.id,
            status=status,
            input_text="test",
            started_at=datetime.now(timezone.utc) if status == "running" else None,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()


def test_recover_stale_runs_marks_pending_and_running_failed():
    pending = _seed_run("pending")
    running = _seed_run("running")

    recover_stale_runs()

    db = SessionLocal()
    try:
        pending_after = db.get(models.WorkflowRun, pending.id)
        running_after = db.get(models.WorkflowRun, running.id)
        assert pending_after is not None
        assert running_after is not None
        assert pending_after.status == "failed"
        assert running_after.status == "failed"
        assert pending_after.final_output == STALE_RUN_MESSAGE
        assert running_after.final_output == STALE_RUN_MESSAGE
        assert pending_after.completed_at is not None
    finally:
        db.close()


def _seed_job(status: str) -> models.BackgroundJob:
    db = SessionLocal()
    try:
        job = models.BackgroundJob(
            id=uuid4(),
            job_type="knowledge_bulk_import",
            status=status,
            user_id=uuid4(),
            payload_json={"documents": []},
            started_at=datetime.now(timezone.utc) if status == "running" else None,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job
    finally:
        db.close()


def test_recover_stale_jobs_marks_running_failed():
    running = _seed_job("running")

    recover_stale_jobs()

    db = SessionLocal()
    try:
        running_after = db.get(models.BackgroundJob, running.id)
        assert running_after is not None
        assert running_after.status == "failed"
        assert running_after.error == STALE_JOB_MESSAGE
        assert running_after.completed_at is not None
    finally:
        db.close()


def test_health_reports_database_status():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["database_ok"] is True
    assert payload["status"] in {"ok", "degraded"}