import json

from app.services.workflow_context import WorkflowContext


def test_context_from_plain_text():
    ctx = WorkflowContext.from_input("hello world")
    data = ctx.to_dict()
    assert data["input"]["text"] == "hello world"
    assert data["last_output"] == "hello world"


def test_context_from_json_input():
    payload = json.dumps({"message": "hi", "priority": "high"})
    ctx = WorkflowContext.from_input(payload)
    data = ctx.to_dict()
    assert data["input"]["message"] == "hi"
    assert data["input"]["text"] == payload


def test_record_step_updates_last_output():
    ctx = WorkflowContext.from_input("start")
    ctx.record_step("n1", "result", label="Agent", node_type="agent")
    data = ctx.to_dict()
    assert data["steps"]["n1"]["output"] == "result"
    assert data["last_output"] == "result"


def test_snapshot_for_metrics_excludes_memory():
    ctx = WorkflowContext.from_input("start")
    ctx.to_dict()["memory"]["secret"] = "do-not-leak"
    snap = ctx.snapshot_for_metrics()
    assert "memory" not in snap
    assert "steps" in snap