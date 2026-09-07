"""Session grouping + tag/session run filters.

Runs carry an optional session_id (a multi-turn thread) and tags. The sessions
endpoint groups runs by session_id; the run list filters by session and tag.
Built on real rows so the join + grouping run end to end.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.db import models
from app.db.database import SessionLocal
from app.main import app

client = TestClient(app)


def _seed(db):
    wf = models.Workflow(id=uuid4(), user_id=DEFAULT_DEV_USER_ID, name="Session WF")
    version = models.WorkflowVersion(
        id=uuid4(), workflow_id=wf.id, version_number=1, graph_json={"nodes": [], "edges": []}
    )
    db.add_all([wf, version])
    db.flush()
    base = datetime.now(timezone.utc).replace(tzinfo=None)
    runs = [
        # Two turns of conversation "conv-a", tagged.
        models.WorkflowRun(id=uuid4(), workflow_version_id=version.id, input_text="hi",
                           status="completed", session_id="conv-a", tags_json=["demo"],
                           created_at=base - timedelta(minutes=10)),
        models.WorkflowRun(id=uuid4(), workflow_version_id=version.id, input_text="more",
                           status="failed", session_id="conv-a", tags_json=["demo"],
                           created_at=base - timedelta(minutes=5)),
        # A different session.
        models.WorkflowRun(id=uuid4(), workflow_version_id=version.id, input_text="x",
                           status="completed", session_id="conv-b",
                           created_at=base - timedelta(minutes=3)),
        # An un-sessioned run (must NOT appear as a session).
        models.WorkflowRun(id=uuid4(), workflow_version_id=version.id, input_text="loose",
                           status="completed", created_at=base - timedelta(minutes=1)),
    ]
    db.add_all(runs)
    db.commit()
    return wf.id


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


def test_sessions_group_by_session_id():
    db = SessionLocal()
    try:
        _seed(db)
        body = client.get("/api/runs/sessions").json()
        by_id = {s["session_id"]: s for s in body["sessions"]}
        assert "conv-a" in by_id and "conv-b" in by_id
        assert by_id["conv-a"]["run_count"] == 2
        assert by_id["conv-a"]["status_counts"] == {"completed": 1, "failed": 1}
        # The un-sessioned run is not a session.
        assert None not in by_id
    finally:
        wf_id = db.query(models.Workflow.id).filter(
            models.Workflow.name == "Session WF"
        ).scalar()
        if wf_id:
            _cleanup(db, wf_id)
        db.close()


def test_list_runs_filters_by_session_and_tag():
    db = SessionLocal()
    try:
        _seed(db)
        by_session = client.get("/api/runs", params={"session_id": "conv-a"}).json()
        assert len(by_session) == 2
        assert all(r["session_id"] == "conv-a" for r in by_session)

        by_tag = client.get("/api/runs", params={"tag": "demo"}).json()
        assert len(by_tag) == 2
        assert all("demo" in r["tags"] for r in by_tag)
    finally:
        wf_id = db.query(models.Workflow.id).filter(
            models.Workflow.name == "Session WF"
        ).scalar()
        if wf_id:
            _cleanup(db, wf_id)
        db.close()
