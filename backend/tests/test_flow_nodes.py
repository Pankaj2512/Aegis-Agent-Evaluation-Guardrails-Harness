import pytest

from app.services.compiler import compile_workflow
from app.services.graph_validation import GraphValidationError, validate_workflow_graph
from tests.conftest import valid_graph


def test_if_node_requires_true_false_edges():
    graph = valid_graph(
        [
            {"id": "if1", "data": {"nodeType": "if", "ifCondition": {"left": "{{input.x}}", "operator": "eq", "right": "1"}}},
            {"id": "a", "data": {"nodeType": "transform", "template": "yes"}},
            {"id": "b", "data": {"nodeType": "transform", "template": "no"}},
            {"id": "join1", "data": {"nodeType": "join"}},
        ],
        [
            {"source": "if1", "target": "a", "label": "true"},
            {"source": "if1", "target": "b", "label": "false"},
            {"source": "a", "target": "join1"},
            {"source": "b", "target": "join1"},
        ],
        exit_id="join1",
    )
    summary = validate_workflow_graph(graph)
    assert summary["node_count"] >= 6


def test_if_missing_branch_rejected():
    graph = valid_graph(
        [
            {"id": "if1", "data": {"nodeType": "if"}},
            {"id": "a", "data": {"nodeType": "transform", "template": "x"}},
        ],
        [{"source": "if1", "target": "a", "label": "true"}],
    )
    with pytest.raises(GraphValidationError, match="false"):
        validate_workflow_graph(graph)


def test_compile_if_switch_nodes():
    graph = valid_graph(
        [
            {"id": "schema", "data": {"nodeType": "input_schema", "inputFields": [{"key": "message"}]}},
            {"id": "if1", "data": {"nodeType": "if", "ifCondition": {"left": "{{input.message}}", "operator": "not_empty"}}},
            {"id": "a", "data": {"nodeType": "set_fields", "setFields": {"ok": "true"}}},
            {"id": "b", "data": {"nodeType": "set_fields", "setFields": {"ok": "false"}}},
            {"id": "join1", "data": {"nodeType": "join"}},
        ],
        [
            {"source": "schema", "target": "if1"},
            {"source": "if1", "target": "a", "label": "true"},
            {"source": "if1", "target": "b", "label": "false"},
            {"source": "a", "target": "join1"},
            {"source": "b", "target": "join1"},
        ],
        entry_id="schema",
        exit_id="join1",
    )
    workflow, metadata, _ = compile_workflow(graph)
    assert workflow.name == "aegis_workflow"
    assert metadata["if1"]["type"] == "if"
    assert metadata["schema"]["type"] == "input_schema"