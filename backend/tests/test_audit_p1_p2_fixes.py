"""Integration coverage for previously-dark critical paths (audit P1/P2).

Targets the exact gaps called out in docs/audit-2026-08-07.md:

* P1-14 — human-approval ``/approve`` transitions (approve→running, deny→failed,
  wrong-status guard) and that the decision is delivered to the per-node
  approval key the executor's ``wait_for_approval`` reads.
* P1-16 — deferred eval fan-out actually runs concurrently and maps
  results/errors per node (the pre-existing test mocked and asserted nothing).
* P1-17 — ``_consume_with_timeout`` charges only active time and is exempt while
  a run is parked ``awaiting_approval`` (the inverted-check bug it prevents).
* P2-17 — retention purge removes child ``run_spans`` explicitly (SQLite has no
  ON DELETE CASCADE), so spans are never orphaned.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.config import settings
from app.db import models
from app.db.database import SessionLocal
from app.main import app
from app.services import approval_service
from app.services import eval_runner
from app.services import executor as executor_service
from app.services.graph_defaults import wrap_graph_with_trigger_end

client = TestClient(app)


def _linear_graph() -> dict:
    return wrap_graph_with_trigger_end(
        [
            {
                "id": "a",
                "position": {"x": 0, "y": 0},
                "data": {"label": "A", "nodeType": "transform", "template": "A"},
            }
        ],
        [],
        entry_id="a",
        exit_id="a",
    )


def _seed_run(status: str, *, metrics: dict | None = None) -> models.WorkflowRun:
    db = SessionLocal()
    try:
        wf = models.Workflow(id=uuid4(), user_id=DEFAULT_DEV_USER_ID, name="Approval WF")
        db.add(wf)
        db.flush()
        version = models.WorkflowVersion(
            id=uuid4(), workflow_id=wf.id, version_number=1, graph_json=_linear_graph()
        )
        db.add(version)
        db.flush()
        run = models.WorkflowRun(
            id=uuid4(),
            workflow_version_id=version.id,
            status=status,
            input_text="hello",
            metrics_json=metrics or {},
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run
    finally:
        db.close()


def _run_status(run_id) -> tuple[str, dict]:
    db = SessionLocal()
    try:
        row = db.query(models.WorkflowRun).filter(models.WorkflowRun.id == run_id).first()
        return row.status, dict(row.metrics_json or {})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# P1-14 — human-approval /approve transitions
# ---------------------------------------------------------------------------


def test_approve_run_resumes_and_delivers_decision_to_node_waiter():
    run = _seed_run(
        "awaiting_approval",
        metrics={"pending_approval": {"node_id": "approve1", "review": "ok?"}},
    )
    approval_service.clear_approval_state(str(run.id))

    resp = client.post(f"/api/runs/{run.id}/approve", json={"approved": True, "comment": "lgtm"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "running"

    status, metrics = _run_status(run.id)
    assert status == "running"
    # pending_approval is cleared; the decision is recorded for the UI.
    assert "pending_approval" not in metrics
    assert metrics["approval_decision"]["approved"] is True
    assert metrics["approval_decision"]["node_id"] == "approve1"

    # The decision is delivered under the per-node key the executor waits on,
    # so wait_for_approval(run_id, node_id="approve1") resolves rather than
    # stranding the run forever.
    decision = asyncio.run(
        approval_service.wait_for_approval(str(run.id), node_id="approve1", timeout=1.0)
    )
    assert decision["approved"] is True
    assert decision["comment"] == "lgtm"
    approval_service.clear_approval_state(str(run.id))


def test_deny_run_marks_failed_with_comment():
    run = _seed_run(
        "awaiting_approval",
        metrics={"pending_approval": {"node_id": "approve1"}},
    )
    approval_service.clear_approval_state(str(run.id))

    resp = client.post(
        f"/api/runs/{run.id}/approve", json={"approved": False, "comment": "nope"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "failed"

    status, metrics = _run_status(run.id)
    assert status == "failed"
    assert metrics["approval_decision"]["approved"] is False
    db = SessionLocal()
    try:
        row = db.query(models.WorkflowRun).filter(models.WorkflowRun.id == run.id).first()
        assert row.final_output == "nope"
        assert row.completed_at is not None
    finally:
        db.close()
    approval_service.clear_approval_state(str(run.id))


def test_approve_rejects_run_not_awaiting_approval():
    run = _seed_run("running")
    resp = client.post(f"/api/runs/{run.id}/approve", json={"approved": True})
    assert resp.status_code == 400
    assert "awaiting approval" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# P1-16 — deferred eval fan-out runs concurrently and maps results/errors
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_parallel_evaluations_runs_concurrently_and_maps_errors(monkeypatch):
    active = 0
    max_active = 0

    async def fake_eval(content, meta, request_context=None):
        nonlocal active, max_active
        if meta.get("boom"):
            raise RuntimeError("eval exploded")
        active += 1
        max_active = max(max_active, active)
        try:
            await asyncio.sleep(0.05)
            return {"aggregate": 4.0, "content": content}
        finally:
            active -= 1

    monkeypatch.setattr(eval_runner, "evaluate_node_async", fake_eval)

    specs = [
        ("n1", {}, "out1"),
        ("n2", {}, "out2"),
        ("n3", {"boom": True}, "out3"),
    ]
    results = await eval_runner.run_parallel_evaluations(specs, request_context="req")

    by_id = {node_id: (scores, err) for node_id, scores, err in results}
    # The two healthy evals ran at the same time — genuine concurrency, not the
    # serial mock the old test asserted nothing about.
    assert max_active >= 2
    assert by_id["n1"][0]["aggregate"] == 4.0
    assert by_id["n2"][0]["content"] == "out2"
    # A failing eval maps to (node_id, None, error) instead of aborting siblings.
    assert by_id["n3"][0] is None
    assert "eval exploded" in by_id["n3"][1]


# ---------------------------------------------------------------------------
# P1-17 — _consume_with_timeout: active-time budget + approval exemption
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_consume_with_timeout_returns_when_work_completes(monkeypatch):
    monkeypatch.setattr(settings, "run_timeout_seconds", 30)

    async def _work():
        return None

    # Completes on the first poll — no timeout.
    await executor_service._consume_with_timeout(uuid4(), _work())


@pytest.mark.asyncio
async def test_consume_with_timeout_times_out_on_active_work(monkeypatch):
    # Sub-poll budget: one 1s active poll (active_elapsed=1.0) exceeds it.
    monkeypatch.setattr(settings, "run_timeout_seconds", 0.5)

    async def _running_status(_run_id):
        return "running"

    monkeypatch.setattr(executor_service, "_read_run_status", _running_status)

    async def _never():
        await asyncio.Event().wait()

    with pytest.raises(asyncio.TimeoutError):
        await executor_service._consume_with_timeout(uuid4(), _never())


@pytest.mark.asyncio
async def test_consume_with_timeout_exempts_awaiting_approval(monkeypatch):
    # Positive budget the awaiting-approval path must never accrue against —
    # the exact inversion this function guards against.
    monkeypatch.setattr(settings, "run_timeout_seconds", 0.5)

    async def _awaiting(_run_id):
        return "awaiting_approval"

    monkeypatch.setattr(executor_service, "_read_run_status", _awaiting)

    async def _never():
        await asyncio.Event().wait()

    task = asyncio.ensure_future(
        executor_service._consume_with_timeout(uuid4(), _never())
    )
    # Span multiple 1s poll intervals; had the budget been charged the function
    # would have raised TimeoutError by now.
    await asyncio.sleep(2.5)
    assert not task.done()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


# ---------------------------------------------------------------------------
# P2-17 — retention purge removes child run_spans (no orphans on SQLite)
# ---------------------------------------------------------------------------


def test_purge_old_runs_removes_child_spans(monkeypatch):
    from app.services.retention import purge_old_runs

    monkeypatch.setattr(settings, "run_retention_days", 30)

    db = SessionLocal()
    try:
        wf = models.Workflow(id=uuid4(), user_id=DEFAULT_DEV_USER_ID, name="Retention WF")
        db.add(wf)
        db.flush()
        version = models.WorkflowVersion(
            id=uuid4(), workflow_id=wf.id, version_number=1, graph_json=_linear_graph()
        )
        db.add(version)
        db.flush()
        old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=200)
        run = models.WorkflowRun(
            id=uuid4(),
            workflow_version_id=version.id,
            status="completed",
            input_text="old",
            created_at=old,
        )
        db.add(run)
        db.flush()
        span = models.RunSpan(
            id=uuid4(), run_id=run.id, kind="node", name="A", status="completed"
        )
        db.add(span)
        db.commit()
        run_id = run.id
        span_id = span.id
    finally:
        db.close()

    deleted = purge_old_runs()
    assert deleted >= 1

    db = SessionLocal()
    try:
        assert (
            db.query(models.WorkflowRun).filter(models.WorkflowRun.id == run_id).first()
            is None
        )
        # The child span must be gone too — not orphaned.
        assert (
            db.query(models.RunSpan).filter(models.RunSpan.id == span_id).first() is None
        )
    finally:
        db.close()
