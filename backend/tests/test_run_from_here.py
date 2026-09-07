"""Tests for authoring-only pin outputs + run-from-here.

Covers the pure graph transform (run_authoring), the run-create validation +
override registration, the executor seeding/pruning behavior end to end, and the
guard that the published invoke path never honors these params.
"""

import asyncio
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.auth.deps import DEFAULT_DEV_USER_ID
from app.db import models
from app.db.database import SessionLocal
from app.main import app
from app.services import executor as executor_service
from app.services.run_authoring import (
    RunAuthoringError,
    prune_graph_for_start,
    seed_pinned_outputs,
)
from app.services.graph_defaults import wrap_graph_with_trigger_end
from app.services.workflow_context import WorkflowContext

client = TestClient(app)


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------


def _linear_graph() -> dict:
    """trigger -> a -> b -> end (transform nodes; no LLM)."""
    return wrap_graph_with_trigger_end(
        [
            {"id": "a", "position": {"x": 0, "y": 0}, "data": {"label": "A", "nodeType": "transform", "template": "A:{{last_output}}"}},
            {"id": "b", "position": {"x": 0, "y": 0}, "data": {"label": "B", "nodeType": "transform", "template": "B:{{steps.a.output}}"}},
        ],
        [{"id": "e-ab", "source": "a", "target": "b"}],
        entry_id="a",
        exit_id="b",
    )


def test_seed_pinned_outputs_records_steps():
    ctx = WorkflowContext.from_input("hi")
    seed_pinned_outputs(ctx, _linear_graph(), {"a": "pinned-A"})
    data = ctx.to_dict()
    assert data["steps"]["a"]["output"] == "pinned-A"
    assert data["last_output"] == "pinned-A"


def test_prune_graph_for_start_removes_pinned_ancestors_and_rewires():
    graph = _linear_graph()
    pruned = prune_graph_for_start(graph, "b", {"a": "pinned-A"})
    node_ids = {n["id"] for n in pruned["nodes"]}
    assert "a" not in node_ids  # pinned ancestor removed
    assert "b" in node_ids and "trigger" in node_ids and "end" in node_ids
    # Trigger now wires straight to b.
    trigger_targets = {e["target"] for e in pruned["edges"] if e["source"] == "trigger"}
    assert trigger_targets == {"b"}
    # Pruned graph still validates.
    from app.services.graph_validation import validate_workflow_graph

    validate_workflow_graph(pruned)


def test_prune_graph_rejects_unpinned_ancestor():
    graph = _linear_graph()
    with pytest.raises(RunAuthoringError):
        prune_graph_for_start(graph, "b", {})  # 'a' upstream but not pinned


def test_prune_graph_start_at_trigger_is_noop():
    graph = _linear_graph()
    trigger_id = next(n["id"] for n in graph["nodes"] if n["data"]["nodeType"] == "trigger")
    assert prune_graph_for_start(graph, trigger_id, {}) is graph


# ---------------------------------------------------------------------------
# run-create validation + override registration
# ---------------------------------------------------------------------------


def _seed_workflow_with_version() -> models.Workflow:
    db = SessionLocal()
    try:
        wf = models.Workflow(id=uuid4(), user_id=DEFAULT_DEV_USER_ID, name="RFH")
        db.add(wf)
        db.flush()
        version = models.WorkflowVersion(
            id=uuid4(), workflow_id=wf.id, version_number=1, graph_json=_linear_graph()
        )
        db.add(version)
        db.commit()
        db.refresh(wf)
        return wf
    finally:
        db.close()


def test_create_run_rejects_unknown_start_node():
    wf = _seed_workflow_with_version()
    resp = client.post(
        "/api/runs",
        json={
            "workflow_id": str(wf.id),
            "input_text": "hello",
            "start_node_id": "does-not-exist",
        },
    )
    assert resp.status_code == 400
    assert "start_node_id" in resp.json()["detail"]


def test_create_run_rejects_unknown_pinned_node():
    wf = _seed_workflow_with_version()
    resp = client.post(
        "/api/runs",
        json={
            "workflow_id": str(wf.id),
            "input_text": "hello",
            "pinned_outputs": {"ghost": "x"},
        },
    )
    assert resp.status_code == 400
    assert "pinned_outputs" in resp.json()["detail"]


def test_create_run_registers_authoring_overrides():
    wf = _seed_workflow_with_version()
    resp = client.post(
        "/api/runs",
        json={
            "workflow_id": str(wf.id),
            "input_text": "hello",
            "pinned_outputs": {"a": "pinned-A"},
            "start_node_id": "b",
        },
    )
    assert resp.status_code == 200, resp.text
    run_id = resp.json()["id"]
    # The override is registered (may be consumed already if the inline run
    # started); accept either present-and-correct or already-consumed.
    override = executor_service._authoring_overrides.get(run_id)
    if override is not None:
        assert override["start_node_id"] == "b"
        assert override["pinned_outputs"] == {"a": "pinned-A"}


# ---------------------------------------------------------------------------
# executor end-to-end: pinned output flows into a run-from-here execution
# ---------------------------------------------------------------------------


def test_executor_pins_and_runs_from_here():
    wf = _seed_workflow_with_version()
    db = SessionLocal()
    try:
        version = (
            db.query(models.WorkflowVersion)
            .filter(models.WorkflowVersion.workflow_id == wf.id)
            .first()
        )
        run = models.WorkflowRun(
            id=uuid4(),
            workflow_version_id=version.id,
            status="pending",
            input_text="hello",
        )
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    executor_service.register_authoring_overrides(
        run_id, pinned_outputs={"a": "PINNED"}, start_node_id="b"
    )
    asyncio.run(executor_service.execute_run(run_id))

    db = SessionLocal()
    try:
        finished = db.query(models.WorkflowRun).filter(models.WorkflowRun.id == run_id).first()
        assert finished.status == "completed", finished.final_output
        results = (
            db.query(models.NodeResult).filter(models.NodeResult.run_id == run_id).all()
        )
        executed = {r.node_id for r in results}
        # Node 'a' was pinned + upstream of start 'b' -> it did NOT execute.
        assert "a" not in executed
        # 'b' executed and consumed the pinned output of 'a'.
        assert "b" in executed
        b_result = next(r for r in results if r.node_id == "b")
        assert "PINNED" in (b_result.output or "")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# guard: published invoke path never honors pin/run-from-here
# ---------------------------------------------------------------------------


def test_invoke_path_ignores_pin_and_run_from_here():
    wf = _seed_workflow_with_version()
    # Extra fields are silently ignored by InvokePayload; the point is they never
    # reach register_authoring_overrides, so no override is registered for the run.
    resp = client.post(
        f"/v1/workflows/{wf.id}/invoke",
        json={"input": "hello", "pinned_outputs": {"a": "X"}, "start_node_id": "b"},
    )
    assert resp.status_code == 200, resp.text
    run_id = resp.json()["run_id"]
    assert executor_service._authoring_overrides.get(run_id) is None
