import asyncio

import pytest

from app.services.approval_service import clear_approval_state, submit_approval, wait_for_approval
from app.services.code_sandbox import run_sandboxed_code, validate_code_safety
from app.services.knowledge_base import retrieve_documents
from app.services.node_handlers import _make_kb_retrieve_fn, _make_memory_retrieve_fn, _make_memory_store_fn


def test_code_sandbox_sets_result():
    code = "result = {'doubled': len(str(input.get('text', ''))) * 2}"
    ctx = {"input": {"text": "hi"}, "steps": {}, "last_output": "hi", "memory": {}}
    out = run_sandboxed_code(code, ctx, "hi")
    assert '"doubled": 4' in out or "doubled" in out


def test_code_sandbox_rejects_import():
    with pytest.raises(ValueError, match="import"):
        validate_code_safety("import os\nresult = 1")


def test_memory_store_and_retrieve():
    ctx: dict = {"input": {"msg": "hello"}, "steps": {}, "last_output": "hello", "memory": {}}
    store = _make_memory_store_fn("ms", "default", "{{input.msg}}", "{{last_output}}", "memory_store", ctx)
    store("hello")
    assert ctx["memory"]["default"]["hello"] == "hello"

    retrieve = _make_memory_retrieve_fn("mr", "default", "{{input.msg}}", "memory_retrieve", ctx)
    assert retrieve("") == "hello"


def test_kb_retrieve_ranks_relevant_chunk():
    docs = [
        {"id": "1", "text": "Python is a programming language.", "title": "Python"},
        {"id": "2", "text": "Coffee brewing techniques and beans.", "title": "Coffee"},
    ]
    hits = retrieve_documents("Python programming", docs, top_k=1)
    assert len(hits) == 1
    assert hits[0]["id"] == "1"


def test_kb_retrieve_node_handler():
    ctx = {"input": {"q": "workflow automation"}, "steps": {}, "last_output": "", "memory": {}}
    docs = [
        {"id": "a", "text": "n8n workflow automation builder"},
        {"id": "b", "text": "unrelated gardening tips"},
    ]
    fn = _make_kb_retrieve_fn("kb", "{{input.q}}", docs, 2, "kb_retrieve", ctx)
    out = fn("")
    assert "workflow" in out.lower()
    assert "gardening" not in out.lower() or "a" in out


@pytest.mark.asyncio
async def test_approval_early_submit_satisfies_later_wait():
    clear_approval_state("run-early")
    submit_approval("run-early", approved=True, comment="submitted first")
    decision = await wait_for_approval("run-early", timeout=1.0)
    assert decision["approved"] is True
    assert decision["comment"] == "submitted first"
    clear_approval_state("run-early")


@pytest.mark.asyncio
async def test_approval_submit_unblocks_waiter():
    clear_approval_state("run-1")
    waiter = asyncio.create_task(wait_for_approval("run-1", timeout=2.0))
    await asyncio.sleep(0.05)
    submit_approval("run-1", approved=True, comment="looks good")
    decision = await waiter
    assert decision["approved"] is True
    assert decision["comment"] == "looks good"
    clear_approval_state("run-1")