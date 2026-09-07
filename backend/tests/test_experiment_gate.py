"""Trust-layer Phase 2: GET /api/experiments/{id}/gate CI regression gate.

Wraps a regression experiment's computed verdict with CI-friendly status
semantics. Seeds experiments in each state and asserts the gate contract.
"""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.db import models
from app.db.database import SessionLocal
from app.main import app

client = TestClient(app)


def _seed_experiment(*, kind: str, status: str, summary: dict | None) -> str:
    db = SessionLocal()
    try:
        # Real parent rows required — SQLite PRAGMA foreign_keys is ON.
        wf = models.Workflow(id=uuid4(), user_id=DEFAULT_DEV_USER_ID, name="Gate WF")
        db.add(wf)
        db.flush()
        version = models.WorkflowVersion(
            id=uuid4(),
            workflow_id=wf.id,
            version_number=1,
            graph_json={"nodes": [], "edges": []},
        )
        baseline = None
        if kind == "regression":
            baseline = models.WorkflowVersion(
                id=uuid4(),
                workflow_id=wf.id,
                version_number=2,
                graph_json={"nodes": [], "edges": []},
            )
        dataset = models.Dataset(
            id=uuid4(),
            user_id=DEFAULT_DEV_USER_ID,
            workflow_id=wf.id,
            name="Gate DS",
        )
        db.add(version)
        if baseline is not None:
            db.add(baseline)
        db.add(dataset)
        db.flush()
        exp = models.Experiment(
            id=uuid4(),
            user_id=DEFAULT_DEV_USER_ID,
            workflow_id=wf.id,
            dataset_id=dataset.id,
            version_id=version.id,
            baseline_version_id=baseline.id if baseline is not None else None,
            kind=kind,
            status=status,
            summary_json=summary,
        )
        db.add(exp)
        db.commit()
        return str(exp.id)
    finally:
        db.close()


def _verdict(passed: bool, eval_delta: float, failure_delta: int, reasons: list[str]) -> dict:
    return {
        "verdict": {
            "passed": passed,
            "eval_delta": eval_delta,
            "failure_delta": failure_delta,
            "max_eval_drop": 0.5,
            "reasons": reasons,
        }
    }


def test_gate_passed_regression():
    exp_id = _seed_experiment(
        kind="regression",
        status="completed",
        summary=_verdict(True, 0.1, 0, ["no regression detected"]),
    )
    resp = client.get(f"/api/experiments/{exp_id}/gate")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "passed"
    assert body["gate_passed"] is True
    assert body["eval_delta"] == 0.1
    assert body["failure_delta"] == 0
    assert body["max_eval_drop"] == 0.5


def test_gate_failed_regression_and_strict_409():
    exp_id = _seed_experiment(
        kind="regression",
        status="completed",
        summary=_verdict(False, -0.8, 2, ["avg eval dropped 0.8 (limit 0.5)", "2 new failure(s)"]),
    )
    resp = client.get(f"/api/experiments/{exp_id}/gate")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "failed"
    assert body["gate_passed"] is False
    assert body["failure_delta"] == 2
    assert len(body["reasons"]) == 2

    # strict mode fails the CI step outright with 409.
    strict = client.get(f"/api/experiments/{exp_id}/gate", params={"strict": "true"})
    assert strict.status_code == 409, strict.text
    assert strict.json()["detail"]["gate_passed"] is False


def test_gate_pending_while_running():
    exp_id = _seed_experiment(kind="regression", status="running", summary=None)
    resp = client.get(f"/api/experiments/{exp_id}/gate")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "pending"
    assert body["gate_passed"] is None
    # strict must not 200 on pending — nothing to pass yet.
    strict = client.get(f"/api/experiments/{exp_id}/gate", params={"strict": "true"})
    assert strict.status_code == 409


def test_gate_not_applicable_for_batch():
    exp_id = _seed_experiment(kind="batch", status="completed", summary={"candidate": {}})
    resp = client.get(f"/api/experiments/{exp_id}/gate")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "not_applicable"


def test_gate_404_for_unknown():
    resp = client.get(f"/api/experiments/{uuid4()}/gate")
    assert resp.status_code == 404
