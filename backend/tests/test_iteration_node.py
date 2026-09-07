"""Tests for the iteration node (map-over-list, Dify-style single-node loop).

The loop lives entirely inside the handler so the workflow graph stays a DAG.
Covers sequential + parallel modes, skip/fail-on-error, the max_items cap, and
sub-workflow-per-item mode (with the sub-workflow call stubbed).
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

import pytest

from app.services.compiler import compile_workflow
from app.services.node_handlers import _make_iteration_fn
from app.services.node_registry import NODE_TYPES_BY_ID
from tests.conftest import valid_graph

_FAKE_WF_ID = "11111111-1111-1111-1111-111111111111"


def _ctx(input_text: str = "start", last_output: str = "a\nb\nc") -> dict:
    return {
        "input": {"text": input_text},
        "steps": {},
        "last_output": last_output,
        "memory": {},
    }


def _run(fn, node_input: str):
    return asyncio.run(fn(node_input))


def _iter_fn(ctx, items_expr, item_tpl="{{item}}", *, sub_id=None, mode="sequential",
             max_items=25, on_error="fail"):
    return _make_iteration_fn(
        "it", items_expr, item_tpl, sub_id, mode, max_items, on_error, "iteration_it", ctx,
    )


def test_iteration_in_registry():
    meta = NODE_TYPES_BY_ID["iteration"]
    assert meta["category"] == "flow"
    assert meta["executable"] is True
    assert meta["supports_expressions"] is True


def test_iteration_compiles():
    graph = valid_graph(
        [
            {"id": "it", "data": {"label": "Loop", "nodeType": "iteration",
                                  "itemsExpression": "{{last_output}}",
                                  "itemTemplate": "X:{{item}}"}},
        ],
    )
    _workflow, metadata, _lookup = compile_workflow(graph)
    assert metadata["it"]["type"] == "iteration"


def test_iteration_sequential_item_template():
    ctx = _ctx()
    fn = _iter_fn(ctx, "{{last_output}}", "item-{{index}}:{{item}}")
    out = json.loads(_run(fn, "a\nb\nc"))
    assert out == ["item-0:a", "item-1:b", "item-2:c"]


def test_iteration_parses_json_array_and_item_fields():
    ctx = _ctx(last_output='[{"name": "x"}, {"name": "y"}]')
    fn = _iter_fn(ctx, "{{last_output}}", "{{item.name}}")
    out = json.loads(_run(fn, "ignored"))
    assert out == ["x", "y"]


def test_iteration_item_template_sees_normal_context():
    ctx = _ctx(input_text="REQ")
    fn = _iter_fn(ctx, '["a", "b"]', "{{input.text}}|{{item}}")
    out = json.loads(_run(fn, "REQ"))
    assert out == ["REQ|a", "REQ|b"]


def test_iteration_object_output_is_parsed():
    ctx = _ctx()
    fn = _iter_fn(ctx, '["a", "b"]', '{"v": "{{item}}"}')
    out = json.loads(_run(fn, "x"))
    assert out == [{"v": "a"}, {"v": "b"}]


def test_iteration_parallel_preserves_order():
    ctx = _ctx()
    fn = _iter_fn(ctx, '["a","b","c","d","e","f","g"]', "v:{{item}}", mode="parallel")
    out = json.loads(_run(fn, "x"))
    assert out == [f"v:{c}" for c in "abcdefg"]


def test_iteration_skip_on_error_records_entry():
    ctx = _ctx()

    async def fake_exec(_wf_id, item_input, **_kwargs):
        if item_input == "b":
            raise RuntimeError("boom")
        return f"ok:{item_input}"

    with patch("app.services.sub_workflow.execute_sub_workflow", side_effect=fake_exec):
        fn = _iter_fn(ctx, '["a","b","c"]', sub_id=_FAKE_WF_ID, on_error="skip")
        out = json.loads(_run(fn, "x"))

    assert out[0] == "ok:a"
    assert out[1] == {"index": 1, "error": "boom"}
    assert out[2] == "ok:c"


def test_iteration_fail_on_error_raises():
    ctx = _ctx()

    async def fake_exec(_wf_id, _item_input, **_kwargs):
        raise RuntimeError("boom")

    with patch("app.services.sub_workflow.execute_sub_workflow", side_effect=fake_exec):
        fn = _iter_fn(ctx, '["a"]', sub_id=_FAKE_WF_ID, on_error="fail")
        with pytest.raises(RuntimeError):
            _run(fn, "x")


def test_iteration_max_items_cap_truncates():
    ctx = _ctx()
    items = json.dumps([str(i) for i in range(40)])
    fn = _iter_fn(ctx, items, "{{item}}", max_items=3)
    out = json.loads(_run(fn, "x"))
    assert out == ["0", "1", "2"]
    note = ctx["_iteration_notes"]["it"]
    assert note["truncated"] is True
    assert note["processed"] == 3
    assert note["total"] == 40


def test_iteration_hard_cap_100():
    ctx = _ctx()
    items = json.dumps([str(i) for i in range(250)])
    # Request above the hard cap is clamped to 100 rather than failing.
    fn = _iter_fn(ctx, items, "{{item}}", max_items=999)
    out = json.loads(_run(fn, "x"))
    assert len(out) == 100


def test_iteration_sub_workflow_mode_feeds_item_as_input():
    ctx = _ctx()
    seen: list[str] = []

    async def fake_exec(_wf_id, item_input, **_kwargs):
        seen.append(item_input)
        return f"processed:{item_input}"

    with patch("app.services.sub_workflow.execute_sub_workflow", side_effect=fake_exec):
        fn = _iter_fn(ctx, '["a", "b"]', sub_id=_FAKE_WF_ID)
        out = json.loads(_run(fn, "x"))

    assert out == ["processed:a", "processed:b"]
    assert seen == ["a", "b"]


def test_iteration_sub_workflow_stringifies_object_items():
    ctx = _ctx()
    seen: list[str] = []

    async def fake_exec(_wf_id, item_input, **_kwargs):
        seen.append(item_input)
        return item_input

    with patch("app.services.sub_workflow.execute_sub_workflow", side_effect=fake_exec):
        fn = _iter_fn(ctx, '[{"k": 1}]', sub_id=_FAKE_WF_ID)
        _run(fn, "x")

    assert seen == ['{"k": 1}']


def test_iteration_newline_fallback():
    ctx = _ctx()
    fn = _iter_fn(ctx, "line one\nline two\n\nline three", "{{item}}")
    out = json.loads(_run(fn, "x"))
    assert out == ["line one", "line two", "line three"]


def test_iteration_empty_items_yields_empty_array():
    ctx = _ctx()
    fn = _iter_fn(ctx, "[]", "{{item}}")
    out = json.loads(_run(fn, "x"))
    assert out == []
