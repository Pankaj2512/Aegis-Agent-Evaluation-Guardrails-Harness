from __future__ import annotations

from collections import defaultdict, deque


class GraphValidationError(ValueError):
    pass


def _node_data(node: dict) -> dict:
    return node.get("data", {}) or {}


def _is_annotation(node: dict) -> bool:
    return _node_data(node).get("nodeType") in {"note", "group"}


# Node types whose failures cannot be intercepted for error-branch routing.
# LLM nodes compile to bare ADK Agent objects (not the wrapped function nodes
# that carry the interception point), and structural nodes have no failure to
# route. Error edges from these are rejected so the UI cannot build dead config.
ERROR_BRANCH_UNSUPPORTED_TYPES = frozenset(
    {
        "trigger",
        "end",
        "note",
        "group",
        "join",
        "agent",
        "summarizer",
        "translator",
        "extractor",
        "evaluation",
    }
)


def _error_branch_unsupported(data: dict) -> bool:
    """True when this node config compiles to a bare ADK Agent (no route interception)."""
    node_type = data.get("nodeType")
    if node_type in ERROR_BRANCH_UNSUPPORTED_TYPES:
        return True
    # Google-search tool nodes compile to a bare Agent with google_search tools —
    # they never set ctx.route, so stamping success edges with __ok__ dead-ends
    # the pipeline. Calculator/http tools are wrapped callables and are fine.
    if (
        node_type == "tool"
        and data.get("toolType") == "search"
        and data.get("searchProvider", "google") == "google"
    ):
        return True
    return False


def _validate_error_edges(nodes: list[dict], edges: list[dict]) -> None:
    """Enforce n8n-style error-branch rules: at most one error edge per node and
    only from node types that support error routing."""
    node_map = {n["id"]: n for n in nodes}
    error_edge_count: dict[str, int] = defaultdict(int)
    for edge in edges:
        if str((edge.get("data") or {}).get("route") or "") != "error":
            continue
        source = edge.get("source")
        error_edge_count[source] += 1
        data = _node_data(node_map.get(source, {}))
        node_type = data.get("nodeType")
        if _error_branch_unsupported(data):
            raise GraphValidationError(
                f"Node '{source}' of type '{node_type}' does not support an "
                "error branch (only non-LLM handler nodes can route on failure)."
            )
    for source, count in error_edge_count.items():
        if count > 1:
            raise GraphValidationError(
                f"Node '{source}' has {count} error edges; at most one error "
                "branch is allowed per node."
            )


def _is_number(value: object) -> bool:
    if value is None or value == "":
        return True  # absent/blank falls back to a default at compile time
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def _validate_numeric_fields(nodes: list[dict]) -> None:
    """Reject non-numeric config for fields the compiler parses as numbers."""
    # (data key, human label, applies-to-node-type or None for all nodes)
    numeric_fields: list[tuple[str, str, str | None]] = [
        ("delaySeconds", "Delay seconds", "delay"),
        ("kbTopK", "Top-K", "kb_retrieve"),
        ("retries", "Retries", None),
        ("retryDelaySec", "Retry delay (sec)", None),
        ("timeoutSec", "Timeout (sec)", None),
    ]
    for node in nodes:
        data = _node_data(node)
        node_type = data.get("nodeType")
        for key, label, only_type in numeric_fields:
            if only_type is not None and node_type != only_type:
                continue
            if key not in data:
                continue
            if not _is_number(data.get(key)):
                raise GraphValidationError(
                    f"Node '{node['id']}' has a non-numeric {label}: "
                    f"{data.get(key)!r}."
                )


def validate_workflow_graph(graph_json: dict) -> dict:
    """Validate canvas graph before save or compile. Returns summary metadata."""
    all_nodes: list[dict] = graph_json.get("nodes", [])
    nodes: list[dict] = [n for n in all_nodes if not _is_annotation(n)]
    node_ids = {n["id"] for n in nodes}
    edges: list[dict] = [
        e
        for e in graph_json.get("edges", [])
        if e.get("source") in node_ids and e.get("target") in node_ids
    ]

    if not nodes:
        raise GraphValidationError("Workflow must contain at least one executable node.")

    node_map = {n["id"]: n for n in nodes}

    indegree: dict[str, int] = {nid: 0 for nid in node_ids}
    outdegree: dict[str, int] = {nid: 0 for nid in node_ids}
    adjacency: dict[str, list[str]] = defaultdict(list)

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source not in node_ids or target not in node_ids:
            raise GraphValidationError(f"Edge references unknown node: {source} -> {target}")
        adjacency[source].append(target)
        indegree[target] += 1
        outdegree[source] += 1

    # Cycle detection (Kahn's algorithm)
    queue: deque[str] = deque([nid for nid, deg in indegree.items() if deg == 0])
    visited = 0
    while queue:
        current = queue.popleft()
        visited += 1
        for neighbor in adjacency[current]:
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    if visited != len(node_ids):
        raise GraphValidationError("Workflow graph must be acyclic (no cycles).")

    trigger_nodes = [n for n in nodes if _node_data(n).get("nodeType") == "trigger"]
    end_nodes = [n for n in nodes if _node_data(n).get("nodeType") == "end"]

    if len(trigger_nodes) != 1:
        raise GraphValidationError(
            f"Workflow must have exactly one Trigger node (found {len(trigger_nodes)})."
        )
    if len(end_nodes) != 1:
        raise GraphValidationError(
            f"Workflow must have exactly one End node (found {len(end_nodes)})."
        )

    trigger_id = trigger_nodes[0]["id"]
    end_id = end_nodes[0]["id"]

    entry_nodes = [nid for nid in node_ids if sum(1 for e in edges if e.get("target") == nid) == 0]
    if len(entry_nodes) != 1:
        raise GraphValidationError(
            f"Workflow must have exactly one entry node (found {len(entry_nodes)})."
        )
    if entry_nodes[0] != trigger_id:
        raise GraphValidationError("Trigger must be the workflow entry node (no incoming edges).")

    # Reachability from entry
    entry = entry_nodes[0]
    reachable: set[str] = set()
    bfs: deque[str] = deque([entry])
    while bfs:
        cur = bfs.popleft()
        if cur in reachable:
            continue
        reachable.add(cur)
        for nxt in adjacency[cur]:
            bfs.append(nxt)

    unreachable = node_ids - reachable
    if unreachable:
        raise GraphValidationError(f"Nodes not reachable from entry: {', '.join(sorted(unreachable))}")

    def _branch_routes(node: dict) -> tuple[str, list[str]]:
        data = _node_data(node)
        node_type = data.get("nodeType")
        if node_type == "router":
            return "route", list(data.get("routes") or [])
        if node_type == "classifier":
            return "category", list(data.get("categories") or [])
        if node_type == "if":
            return "branch", ["true", "false"]
        if node_type == "switch":
            cases = list(data.get("switchCases") or [])
            default_route = data.get("switchDefault", "default")
            return "case", [*cases, default_route]
        if node_type == "guardrail":
            rules = data.get("rules") or {}
            if rules.get("fail_behavior") == "route":
                return "route", [
                    str(rules.get("pass_route") or "pass"),
                    str(rules.get("failure_route") or "failed"),
                ]
        return "", []

    # Branching nodes must wire all routes to outgoing edges
    for node in nodes:
        label, routes = _branch_routes(node)
        if not routes:
            node_type = _node_data(node).get("nodeType")
            if node_type in {"router", "classifier"}:
                raise GraphValidationError(
                    f"{node_type.title()} node '{node['id']}' must define at least one {label}."
                )
            continue
        outgoing = [e for e in edges if e.get("source") == node["id"]]
        edge_routes = {(e.get("data") or {}).get("route") or e.get("label") for e in outgoing}
        edge_routes.discard(None)
        for route in routes:
            if route not in edge_routes:
                node_type = _node_data(node).get("nodeType", "branch")
                raise GraphValidationError(
                    f"{node_type.title()} '{node['id']}' {label} '{route}' "
                    "has no outgoing edge with matching label."
                )

    _validate_numeric_fields(nodes)
    _validate_error_edges(nodes, edges)

    terminal_nodes = [nid for nid in node_ids if outdegree[nid] == 0]
    if len(terminal_nodes) != 1 or terminal_nodes[0] != end_id:
        raise GraphValidationError(
            "Workflow must end at exactly one End node with no outgoing connections."
        )

    if end_id not in reachable:
        raise GraphValidationError("End node must be reachable from Trigger.")

    join_nodes = [n["id"] for n in nodes if (n.get("data") or {}).get("nodeType") == "join"]

    return {
        "node_count": len(nodes),
        "annotation_count": len(all_nodes) - len(nodes),
        "edge_count": len(edges),
        "entry_node": entry,
        "exit_node": end_id,
        "trigger_node": trigger_id,
        "terminal_nodes": terminal_nodes,
        "join_nodes": join_nodes,
        "has_router": any((n.get("data") or {}).get("nodeType") == "router" for n in nodes),
        "has_parallel": any(outdegree[nid] > 1 for nid in node_ids),
    }