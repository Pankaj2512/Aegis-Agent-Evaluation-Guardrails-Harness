import pytest
from google.genai import types

from app.services.compiler import _safe_eval, compile_workflow, topological_sort
from tests.conftest import valid_graph


def test_topological_sort_linear():
    nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    edges = [
        {"source": "a", "target": "b"},
        {"source": "b", "target": "c"},
    ]
    assert topological_sort(nodes, edges) == ["a", "b", "c"]


def test_topological_sort_rejects_cycles():
    nodes = [{"id": "a"}, {"id": "b"}]
    edges = [
        {"source": "a", "target": "b"},
        {"source": "b", "target": "a"},
    ]
    with pytest.raises(ValueError, match="acyclic"):
        topological_sort(nodes, edges)


def test_compile_workflow_metadata_adk_names():
    graph = valid_graph(
        [
            {
                "id": "n1",
                "data": {"label": "Agent", "nodeType": "agent", "instruction": "Hi"},
            },
            {
                "id": "n2",
                "data": {"label": "Guard", "nodeType": "guardrail", "rules": {}},
            },
        ],
        [{"source": "n1", "target": "n2"}],
    )
    workflow, metadata, _author_lookup = compile_workflow(graph)
    assert workflow.name == "aegis_workflow"
    assert metadata["n1"]["node_id"] == "n1"
    assert metadata["n2"]["node_id"] == "n2"
    assert "agent" in metadata["n1"]["adk_name"]
    assert "guardrail" in metadata["n2"]["adk_name"]


def test_compile_google_search_enables_server_side_tool_invocations():
    graph = valid_graph(
        [
            {
                "id": "n1",
                "data": {
                    "label": "Web Search",
                    "nodeType": "tool",
                    "toolType": "search",
                    "searchProvider": "google",
                },
            },
            {
                "id": "n2",
                "data": {"label": "Agent", "nodeType": "agent", "instruction": "Summarize"},
            },
        ],
        [{"source": "n1", "target": "n2"}],
    )
    workflow, metadata, _author_lookup = compile_workflow(graph)
    search_adk_name = metadata["n1"]["adk_name"]
    search_node = next(
        edge.from_node for edge in workflow.edges if edge.from_node.name == search_adk_name
    )
    assert metadata["n1"]["searchProvider"] == "google"
    assert search_node.generate_content_config is not None
    assert search_node.generate_content_config.tool_config == types.ToolConfig(
        include_server_side_tool_invocations=True,
    )


def test_safe_eval_blocks_large_exponent():
    result = _safe_eval("9**9**9")
    assert "Calculator error" in result
    assert "exponent" in result.lower()


def test_safe_eval_allows_simple_pow():
    assert _safe_eval("2**10") == "1024.0"