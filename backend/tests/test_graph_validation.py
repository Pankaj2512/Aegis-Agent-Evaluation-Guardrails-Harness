import pytest

from app.services.graph_validation import GraphValidationError, validate_workflow_graph
from tests.conftest import valid_graph


def test_valid_linear_graph():
    graph = valid_graph(
        [
            {"id": "a", "data": {"nodeType": "agent"}},
            {"id": "b", "data": {"nodeType": "evaluation"}},
        ],
        [{"source": "a", "target": "b"}],
    )
    summary = validate_workflow_graph(graph)
    assert summary["entry_node"] == "trigger"
    assert summary["exit_node"] == "end"
    assert summary["node_count"] == 4


def test_group_nodes_treated_as_annotation():
    graph = valid_graph(
        [
            {"id": "a", "data": {"nodeType": "agent"}},
            {"id": "grp", "data": {"nodeType": "group"}},
        ],
        [],
    )
    summary = validate_workflow_graph(graph)
    # group node is excluded from executable nodes, like a sticky note
    assert summary["annotation_count"] == 1
    assert summary["node_count"] == 3  # trigger, a, end


def test_rejects_cycle():
    graph = valid_graph(
        [
            {"id": "a", "data": {"nodeType": "agent"}},
            {"id": "b", "data": {"nodeType": "agent"}},
        ],
        [
            {"source": "a", "target": "b"},
            {"source": "b", "target": "a"},
        ],
    )
    with pytest.raises(GraphValidationError, match="acyclic"):
        validate_workflow_graph(graph)


def test_rejects_missing_trigger():
    graph = {
        "nodes": [
            {"id": "a", "data": {"nodeType": "agent"}},
            {"id": "end", "data": {"nodeType": "end"}},
        ],
        "edges": [{"source": "a", "target": "end"}],
    }
    with pytest.raises(GraphValidationError, match="exactly one Trigger"):
        validate_workflow_graph(graph)


def test_rejects_missing_end():
    graph = {
        "nodes": [
            {"id": "trigger", "data": {"nodeType": "trigger"}},
            {"id": "a", "data": {"nodeType": "agent"}},
        ],
        "edges": [{"source": "trigger", "target": "a"}],
    }
    with pytest.raises(GraphValidationError, match="exactly one End"):
        validate_workflow_graph(graph)


def test_rejects_end_not_terminal():
    graph = {
        "nodes": [
            {"id": "trigger", "data": {"nodeType": "trigger"}},
            {"id": "end", "data": {"nodeType": "end"}},
            {"id": "a", "data": {"nodeType": "agent"}},
            {"id": "b", "data": {"nodeType": "agent"}},
        ],
        "edges": [
            {"source": "trigger", "target": "a"},
            {"source": "a", "target": "end"},
            {"source": "end", "target": "b"},
        ],
    }
    with pytest.raises(GraphValidationError, match="End node"):
        validate_workflow_graph(graph)


def test_router_validation_handles_null_edge_data():
    graph = valid_graph(
        [
            {
                "id": "router",
                "data": {"nodeType": "router", "routes": ["a", "b"]},
            },
            {"id": "left", "data": {"nodeType": "agent"}},
            {"id": "right", "data": {"nodeType": "agent"}},
            {"id": "join", "data": {"nodeType": "join"}},
        ],
        [
            {"source": "router", "target": "left", "data": None, "label": "a"},
            {"source": "router", "target": "right", "data": None, "label": "b"},
            {"source": "left", "target": "join"},
            {"source": "right", "target": "join"},
        ],
        exit_id="join",
    )
    summary = validate_workflow_graph(graph)
    assert summary["has_router"] is True