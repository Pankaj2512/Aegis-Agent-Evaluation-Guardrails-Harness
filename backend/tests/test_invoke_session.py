"""session_id / tags flow through the external run-creation paths.

The ingest endpoint records runs without executing, so it's the clean path to
assert that a caller-supplied session_id threads runs into one session (which
then surfaces in /api/runs/sessions).
"""

from fastapi.testclient import TestClient

from app.db import models
from app.db.database import SessionLocal
from app.main import app

client = TestClient(app)

_WF = "Ingest Session WF"


def _ingest(session_id, text):
    return client.post(
        "/v1/ingest/runs",
        json={
            "workflow_name": _WF,
            "input": text,
            "output": "ok",
            "status": "completed",
            "session_id": session_id,
            "tags": ["chat"],
        },
    )


def test_ingest_threads_runs_into_a_session():
    try:
        assert _ingest("chat-thread-1", "turn one").status_code == 201
        assert _ingest("chat-thread-1", "turn two").status_code == 201
        assert _ingest("chat-thread-2", "other").status_code == 201

        sessions = client.get("/api/runs/sessions").json()["sessions"]
        by_id = {s["session_id"]: s for s in sessions}
        assert by_id["chat-thread-1"]["run_count"] == 2
        assert "chat-thread-2" in by_id

        # And the runs carry the session + tag through the run list filter.
        runs = client.get("/api/runs", params={"session_id": "chat-thread-1"}).json()
        assert len(runs) == 2
        assert all("chat" in r["tags"] for r in runs)
    finally:
        db = SessionLocal()
        try:
            wf = db.query(models.Workflow).filter(models.Workflow.name == _WF).first()
            if wf:
                version_ids = db.query(models.WorkflowVersion.id).filter(
                    models.WorkflowVersion.workflow_id == wf.id
                )
                db.query(models.WorkflowRun).filter(
                    models.WorkflowRun.workflow_version_id.in_(version_ids)
                ).delete(synchronize_session=False)
                db.query(models.WorkflowVersion).filter(
                    models.WorkflowVersion.workflow_id == wf.id
                ).delete(synchronize_session=False)
                db.query(models.Workflow).filter(models.Workflow.id == wf.id).delete(
                    synchronize_session=False
                )
                db.commit()
        finally:
            db.close()
