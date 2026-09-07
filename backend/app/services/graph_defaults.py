"""Helpers for standard Trigger → … → End workflow graphs."""

from __future__ import annotations

from copy import deepcopy

TRIGGER_NODE: dict = {
    "id": "trigger",
    "position": {"x": 40, "y": 120},
    "data": {
        "label": "Trigger",
        "nodeType": "trigger",
        "triggerType": "manual",
    },
}

END_NODE: dict = {
    "id": "end",
    "position": {"x": 880, "y": 120},
    "data": {
        "label": "End",
        "nodeType": "end",
    },
}

INPUT_SCHEMA_NODE_ID = "input_schema"


def wrap_graph_with_trigger_end(
    nodes: list[dict],
    edges: list[dict],
    *,
    entry_id: str | None = None,
    exit_id: str | None = None,
    input_fields: list[dict] | None = None,
    trigger_type: str = "manual",
    schedule_cron: str | None = None,
) -> dict:
    """Prepend Trigger and append End, wiring entry/exit automatically.

    When ``input_fields`` is set, inserts an Input Schema node after Trigger
    (Lyzr-style structured workflow inputs).
    """
    body = deepcopy(nodes)
    body_edges = deepcopy(edges)

    executable = [
        n for n in body if (n.get("data") or {}).get("nodeType") not in {"note", "group"}
    ]

    if not entry_id and executable:
        indegree = {n["id"]: 0 for n in executable}
        for edge in body_edges:
            target = edge.get("target")
            if target in indegree:
                indegree[target] += 1
        entries = [nid for nid, deg in indegree.items() if deg == 0]
        entry_id = entries[0] if len(entries) == 1 else executable[0]["id"]

    if not exit_id and executable:
        outdegree = {n["id"]: 0 for n in executable}
        for edge in body_edges:
            source = edge.get("source")
            if source in outdegree:
                outdegree[source] += 1
        exits = [nid for nid, deg in outdegree.items() if deg == 0]
        exit_id = exits[0] if len(exits) == 1 else executable[-1]["id"]

    trigger = deepcopy(TRIGGER_NODE)
    trigger["data"]["triggerType"] = trigger_type
    if trigger_type == "schedule" and schedule_cron:
        trigger["data"]["scheduleCron"] = schedule_cron
    end = deepcopy(END_NODE)
    end["position"] = {
        "x": max((n.get("position") or {}).get("x", 0) for n in body) + 260,
        "y": 120,
    }

    schema_node: dict | None = None
    if input_fields:
        schema_node = {
            "id": INPUT_SCHEMA_NODE_ID,
            "position": {"x": 200, "y": 120},
            "data": {
                "label": "Input Schema",
                "nodeType": "input_schema",
                "inputFields": input_fields,
            },
        }

    wrapped_nodes = [trigger, *( [schema_node] if schema_node else []), *body, end]
    if schema_node:
        wrapped_edges = [
            {"id": "e-trigger-schema", "source": "trigger", "target": INPUT_SCHEMA_NODE_ID},
            {"id": "e-schema-entry", "source": INPUT_SCHEMA_NODE_ID, "target": entry_id},
            {"id": "e-exit-end", "source": exit_id, "target": "end"},
            *body_edges,
        ]
    else:
        wrapped_edges = [
            {"id": "e-trigger-entry", "source": "trigger", "target": entry_id},
            {"id": "e-exit-end", "source": exit_id, "target": "end"},
            *body_edges,
        ]
    return {"nodes": wrapped_nodes, "edges": wrapped_edges}