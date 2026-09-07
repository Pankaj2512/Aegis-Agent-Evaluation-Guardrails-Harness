"""Bulk capture of production runs into a golden dataset.

Covers the filter modes (failed / low_eval) and dedup by source_run. Seeds real
rows, calls the endpoint via the API, and asserts on what lands in the dataset.
"""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.db import models
from app.db.database import SessionLocal
from app.main import app

client = TestClient(app)


def _seed(db):
    # Flush parents before children — with PRAGMA foreign_keys=ON, SQLite
    # rejects out-of-order inserts from a single add_all flush.
    wf = models.Workflow(id=uuid4(), user_id=DEFAULT_DEV_USER_ID, name="Capture WF")
    db.add(wf)
    db.flush()
    version = models.WorkflowVersion(
        id=uuid4(), workflow_id=wf.id, version_number=1, graph_json={"nodes": [], "edges": []}
    )
    dataset = models.Dataset(id=uuid4(), user_id=DEFAULT_DEV_USER_ID, workflow_id=wf.id, name="Golden")
    db.add(version)
    db.add(dataset)
    db.flush()
    runs = [
        models.WorkflowRun(id=uuid4(), workflow_version_id=version.id, input_text="ok run",
                           status="completed", final_output="fine",
                           metrics_json={"eval_aggregate": 4.5}),
        models.WorkflowRun(id=uuid4(), workflow_version_id=version.id, input_text="weak run",
                           status="completed", final_output="meh",
                           metrics_json={"eval_aggregate": 2.0}),
        models.WorkflowRun(id=uuid4(), workflow_version_id=version.id, input_text="boom run",
                           status="failed", final_output="error"),
    ]
    db.add_all(runs)
    db.commit()
    return wf.id, dataset.id


def _cleanup(db, workflow_id, dataset_id):
    db.query(models.DatasetItem).filter(models.DatasetItem.dataset_id == dataset_id).delete(
        synchronize_session=False
    )
    db.query(models.Dataset).filter(models.Dataset.id == dataset_id).delete(synchronize_session=False)
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


def test_capture_failed_then_dedups():
    db = SessionLocal()
    wf_id = ds_id = None
    try:
        wf_id, ds_id = _seed(db)
        first = client.post(f"/api/datasets/{ds_id}/capture", json={"filter": "failed", "limit": 20}).json()
        assert first["added"] == 1  # only the failed run
        # Re-capture: the run is already in the set, so it's skipped, not duplicated.
        second = client.post(f"/api/datasets/{ds_id}/capture", json={"filter": "failed", "limit": 20}).json()
        assert second["added"] == 0 and second["skipped"] >= 1

        detail = client.get(f"/api/datasets/{ds_id}").json()
        assert detail["item_count"] == 1
        assert detail["items"][0]["input_text"] == "boom run"
    finally:
        if wf_id:
            _cleanup(db, wf_id, ds_id)
        db.close()


def test_capture_low_eval():
    db = SessionLocal()
    wf_id = ds_id = None
    try:
        wf_id, ds_id = _seed(db)
        result = client.post(
            f"/api/datasets/{ds_id}/capture", json={"filter": "low_eval", "limit": 20, "max_eval": 3.0}
        ).json()
        # Only the eval_aggregate=2.0 run is below 3.0 (4.5 excluded, failed has no eval).
        assert result["added"] == 1
        detail = client.get(f"/api/datasets/{ds_id}").json()
        assert detail["items"][0]["input_text"] == "weak run"
    finally:
        if wf_id:
            _cleanup(db, wf_id, ds_id)
        db.close()
