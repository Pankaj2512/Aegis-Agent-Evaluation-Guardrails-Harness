"""Authoring-only run helpers: pin outputs + run-from-here.

These features let the builder UI re-run a workflow from a chosen node while
feeding pre-recorded ("pinned") outputs for the upstream nodes it skips. This is
ONLY ever reachable from the authenticated run-create path — the published
``/v1/workflows/{id}/invoke`` path must not honor it (guarded in the API layer).

The transform is pure and graph-level:
  * seed pinned outputs into the WorkflowContext (steps + last_output), and
  * prune the graph so the trigger connects directly to ``start_node_id`` and
    strictly-upstream nodes whose outputs are pinned are removed.

Nothing here touches the database or the stored workflow.
"""

from __future__ import annotations

from collections import defaultdict, deque
from copy import deepcopy
from typing import Any

from app.services.workflow_context import WorkflowContext


class RunAuthoringError(ValueError):
    """Raised when pin/run-from-here parameters are invalid for the graph."""


def _node_data(node: dict) -> dict:
    return node.get("data") or {}


def _node_type(node: dict) -> str:
    return _node_data(node).get("nodeType", "")


def seed_pinned_outputs(
    context: WorkflowContext,
    graph_json: dict,
    pinned_outputs: dict[str, Any],
) -> None:
    """Record each pinned node output into the context as a completed step."""
    nodes_by_id = {n.get("id"): n for n in graph_json.get("nodes", [])}
    last_value: str | None = None
    for node_id, value in pinned_outputs.items():
        node = nodes_by_id.get(node_id)
        data = _node_data(node) if node else {}
        text = value if isinstance(value, str) else str(value)
        context.record_step(
            node_id,
            text,
            label=data.get("label") or node_id,
            node_type=data.get("nodeType"),
        )
        last_value = text
    # record_step already updated last_output for each; leave it on the final
    # pinned value so a start node reading {{last_output}} sees its predecessor.
    if last_value is not None:
        context.set_last_output(last_value)


def _ancestors(node_id: str, edges: list[dict]) -> set[str]:
    """All nodes that can reach ``node_id`` (strict upstream set)."""
    incoming: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        incoming[edge.get("target")].append(edge.get("source"))
    seen: set[str] = set()
    queue: deque[str] = deque([node_id])
    while queue:
        cur = queue.popleft()
        for src in incoming.get(cur, []):
            if src and src not in seen:
                seen.add(src)
                queue.append(src)
    return seen


def prune_graph_for_start(
    graph_json: dict,
    start_node_id: str,
    pinned_outputs: dict[str, Any],
) -> dict:
    """Return a new graph that begins execution at ``start_node_id``.

    Strictly-upstream nodes whose outputs are pinned are removed; the trigger is
    rewired directly to the start node so validation (single trigger -> ... ->
    single end) still holds. The trigger and end nodes are always retained.
    """
    nodes: list[dict] = deepcopy(graph_json.get("nodes", []))
    edges: list[dict] = deepcopy(graph_json.get("edges", []))
    nodes_by_id = {n.get("id"): n for n in nodes}

    if start_node_id not in nodes_by_id:
        raise RunAuthoringError(f"start_node_id '{start_node_id}' not found in graph.")

    trigger_ids = [n["id"] for n in nodes if _node_type(n) == "trigger"]
    if not trigger_ids:
        raise RunAuthoringError("Graph has no trigger node.")
    trigger_id = trigger_ids[0]

    if start_node_id == trigger_id:
        # Nothing to prune; run normally.
        return graph_json

    ancestors = _ancestors(start_node_id, edges)
    # Only remove ancestors that are pinned (so their output is available) and
    # are not the trigger itself.
    removable = {
        nid
        for nid in ancestors
        if nid in pinned_outputs and nid != trigger_id
    }

    # Any un-pinned ancestor (other than the trigger) means we would execute an
    # upstream node with no seeded input — reject to keep behavior predictable.
    unpinned_ancestors = {
        nid for nid in ancestors if nid != trigger_id and nid not in pinned_outputs
    }
    if unpinned_ancestors:
        raise RunAuthoringError(
            "Cannot run from node "
            f"'{start_node_id}': upstream node(s) {sorted(unpinned_ancestors)} "
            "are not pinned. Pin their outputs or start earlier."
        )

    kept_nodes = [n for n in nodes if n["id"] not in removable]
    kept_ids = {n["id"] for n in kept_nodes}

    # Drop edges touching removed nodes.
    kept_edges = [
        e
        for e in edges
        if e.get("source") in kept_ids and e.get("target") in kept_ids
    ]

    # Rewire the trigger straight to the start node (single unconditional edge).
    kept_edges = [
        e for e in kept_edges if e.get("source") != trigger_id
    ]
    kept_edges.append(
        {
            "id": f"e-{trigger_id}-{start_node_id}",
            "source": trigger_id,
            "target": start_node_id,
        }
    )

    return {"nodes": kept_nodes, "edges": kept_edges}
