"""AI-assist services: workflow generation, node suggestions, run explanation.

All three features wrap Gemini (google.genai) with structured output, following
the pattern in app/services/guardrail.py. Node config is round-tripped as a
JSON string because Gemini's response_schema cannot express free-form dicts.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict, deque
from threading import Lock
from typing import Any

from fastapi import HTTPException, status

from app.config import settings
from app.schemas.assist import (
    AssistHistoryTurn,
    CompareRequest,
    CompareVariantResult,
    EditGraphResponse,
    ExplainRunResponse,
    GeneratedWorkflowDraft,
    GenerateSchemaResponse,
    GraphDiff,
    NodeSuggestion,
    SuggestedFix,
    SuggestionsDraft,
    _EditGraphDraft,
    _GeneratedSchemaDraft,
)
from app.services.graph_validation import GraphValidationError, validate_workflow_graph
from app.services.node_registry import NODE_REGISTRY, NODE_TYPES_BY_ID


class AssistError(Exception):
    """Raised when the assistant cannot produce a usable result (mapped to 422)."""


# ---------------------------------------------------------------------------
# Node catalog prompt (built once at import)
# ---------------------------------------------------------------------------

# Required / important data keys per node type, derived from compiler.py and
# node_handlers.py — NOT guessed. Config is nested under node ``data``.
_REQUIRED_DATA_KEYS: dict[str, str] = {
    "trigger": "triggerType (manual|webhook|schedule)",
    "end": "(no config)",
    "input_schema": "inputFields: [{key, type, required}]",
    "if": "ifCondition: {left, operator, right}; branches route 'true'/'false'",
    "switch": "switchValue, switchCases: [str], switchDefault; one edge per case + default",
    "filter": "filterCondition: {left, operator, right}",
    "agent": "instruction (system prompt)",
    "summarizer": "summaryStyle",
    "translator": "targetLanguage",
    "extractor": "extractFields: [str]",
    "tool": "toolType (calculator|http|search); http needs httpUrl/httpMethod; search needs searchProvider",
    "transform": "template (with {{expressions}})",
    "set_fields": "setFields: {key: value}",
    "code": "code (sandboxed Python; set `result`)",
    "memory_store": "memoryNamespace, memoryKey, memoryValue",
    "memory_retrieve": "memoryNamespace, memoryKey",
    "kb_retrieve": "kbQuery, kbDocuments: [{id,title,text}], kbTopK (needs KB docs configured)",
    "human_approval": "approvalReview",
    "sub_workflow": "subWorkflowId, subWorkflowInput",
    "integration": "integrationType (slack|discord|email|postgres); needs credentialId/credentialName + a message/body/query",
    "json_parse": "jsonPath",
    "delay": "delaySeconds",
    "evaluation": "evalPreset or criteria, evalType",
    "guardrail": "rules: {guardrail_type, blocked_keywords, fail_behavior}; fail_behavior='route' branches pass/failed",
    "router": "routes: [str]; one outgoing edge per route (edge route set)",
    "classifier": "categories: [str]; one outgoing edge per category (edge route set)",
    "join": "(no config; fan-in for parallel branches)",
}


def _node_catalog_prompt() -> str:
    lines: list[str] = ["AVAILABLE NODE TYPES (node_type — label [category]: description | data keys):"]
    for meta in NODE_REGISTRY:
        node_type = meta["type"]
        if not meta.get("executable", True):
            continue  # skip annotation-only nodes (note)
        label = meta.get("label", node_type)
        category = meta.get("category", "")
        description = meta.get("description", "")
        branching = " [BRANCHING]" if meta.get("branches") else ""
        keys = _REQUIRED_DATA_KEYS.get(node_type, "")
        desc = f": {description}" if description else ""
        lines.append(
            f"- {node_type} — {label} [{category}]{branching}{desc} | data: {keys}"
        )
    return "\n".join(lines)


_NODE_CATALOG = _node_catalog_prompt()


_GRAPH_RULES = (
    "GRAPH RULES (validation is strict — a workflow that breaks any rule is rejected):\n"
    "- Exactly ONE 'trigger' node; it is the entry (no incoming edges).\n"
    "- Exactly ONE 'end' node; it is the sole terminal (no outgoing edges) and must be reachable.\n"
    "- The graph must be acyclic (no cycles).\n"
    "- Every node must be reachable from the trigger.\n"
    "- Branching nodes (router/classifier/if/switch, and guardrail with fail_behavior='route') "
    "must have one outgoing edge per route, and each such edge MUST set its 'route' to the "
    "matching route/category/branch/case value.\n"
    "- Non-branch nodes have a single unlabelled outgoing edge (route null).\n"
    "- Put node configuration in config_json as a JSON object string (e.g. "
    '"{\\"instruction\\": \\"...\\"}"). Use null when a node needs no config.\n'
)


_FEW_SHOT = """EXAMPLE 1 — simple agent flow
{
  "nodes": [
    {"id": "trigger", "node_type": "trigger", "label": "Trigger", "config_json": "{\\"triggerType\\": \\"manual\\"}"},
    {"id": "agent", "node_type": "agent", "label": "LLM Agent", "config_json": "{\\"instruction\\": \\"You are a helpful assistant. Answer the user clearly.\\"}"},
    {"id": "end", "node_type": "end", "label": "End", "config_json": null}
  ],
  "edges": [
    {"source": "trigger", "target": "agent", "route": null},
    {"source": "agent", "target": "end", "route": null}
  ],
  "notes": ["Refine the agent instruction for your use case."]
}

EXAMPLE 2 — classifier with two branches
{
  "nodes": [
    {"id": "trigger", "node_type": "trigger", "label": "Intake", "config_json": "{\\"triggerType\\": \\"manual\\"}"},
    {"id": "classify", "node_type": "classifier", "label": "Classify request", "config_json": "{\\"categories\\": [\\"billing\\", \\"support\\"]}"},
    {"id": "billing", "node_type": "agent", "label": "Billing reply", "config_json": "{\\"instruction\\": \\"Answer the billing question.\\"}"},
    {"id": "support", "node_type": "agent", "label": "Support reply", "config_json": "{\\"instruction\\": \\"Answer the support question.\\"}"},
    {"id": "end", "node_type": "end", "label": "End", "config_json": null}
  ],
  "edges": [
    {"source": "trigger", "target": "classify", "route": null},
    {"source": "classify", "target": "billing", "route": "billing"},
    {"source": "classify", "target": "support", "route": "support"},
    {"source": "billing", "target": "end", "route": null},
    {"source": "support", "target": "end", "route": null}
  ],
  "notes": ["Both branch agents share one End node."]
}
"""


# ---------------------------------------------------------------------------
# Conversational history (threaded copilot turns)
# ---------------------------------------------------------------------------

# Keep the copilot cheap and bounded: only the most recent turns are ever sent
# to the model or folded into a cache key. Truncation is silent — an over-long
# history is trimmed, never rejected.
_HISTORY_MAX_TURNS = 8


def _capped_history(
    history: list[AssistHistoryTurn] | None,
) -> list[AssistHistoryTurn]:
    """Last ``_HISTORY_MAX_TURNS`` turns with usable content, oldest first."""
    if not history:
        return []
    kept = [turn for turn in history if turn.content and turn.content.strip()]
    return kept[-_HISTORY_MAX_TURNS:]


def _format_history(history: list[AssistHistoryTurn] | None) -> str:
    """Render prior turns as a prompt block, or "" when there is nothing to add.

    Empty/absent history yields "" so the prompt is byte-identical to the
    non-threaded path (back-compat).
    """
    turns = _capped_history(history)
    if not turns:
        return ""
    lines: list[str] = [
        "PRIOR CONVERSATION (oldest first) — the user's new instruction may refer "
        "back to these earlier turns (e.g. 'undo that', 'make the second branch "
        "stricter'). Resolve such references against this history:"
    ]
    for turn in turns:
        speaker = "User" if turn.role == "user" else "Assistant"
        lines.append(f"{speaker}: {turn.content.strip()}")
    return "\n".join(lines)


def _history_cache_fragment(history: list[AssistHistoryTurn] | None) -> str:
    """Stable digest fragment for the capped history, for cache keying.

    Empty history returns "" so history-free callers keep their prior cache key
    shape and turn-3 requests never collide with turn-1 cache entries.
    """
    turns = _capped_history(history)
    if not turns:
        return ""
    payload = json.dumps([[t.role, t.content.strip()] for t in turns], sort_keys=False)
    return hashlib.sha256(payload.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Gemini client helper
# ---------------------------------------------------------------------------


def _gemini_config(response_schema: type, timeout_seconds: int) -> dict[str, Any]:
    return {
        "response_mime_type": "application/json",
        "response_schema": response_schema,
        "http_options": {"timeout": timeout_seconds * 1000},
    }


def _generate_content(prompt: str, response_schema: type, timeout_seconds: int) -> str:
    from google import genai

    client = genai.Client(api_key=settings.google_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=_gemini_config(response_schema, timeout_seconds),
    )
    return response.text or "{}"


# ---------------------------------------------------------------------------
# Layout port (from frontend WorkflowCanvas.tsx handleTidyLayout)
# ---------------------------------------------------------------------------


def _assign_positions(graph: dict) -> dict:
    """Layer nodes left-to-right by BFS depth from entry nodes.

    Faithful port of the frontend tidy layout: x = 60 + depth*280,
    y = 60 + offset + i*140, with shorter columns vertically centered.
    Mutates node ``position`` in place and returns the graph.
    """
    nodes: list[dict] = graph.get("nodes", [])
    edges: list[dict] = graph.get("edges", [])
    if not nodes:
        return graph

    adj: dict[str, list[str]] = defaultdict(list)
    incoming: dict[str, int] = {n["id"]: 0 for n in nodes}
    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source in incoming and target in incoming:
            adj[source].append(target)
            incoming[target] += 1

    depth: dict[str, int] = {}
    queue: deque[str] = deque(n["id"] for n in nodes if incoming.get(n["id"], 0) == 0)
    for nid in queue:
        depth[nid] = 0
    while queue:
        nid = queue.popleft()
        d = depth.get(nid, 0) + 1
        if d > len(nodes):  # cycle guard
            continue
        for nxt in adj.get(nid, []):
            if depth.get(nxt, -1) < d:
                depth[nxt] = d
                queue.append(nxt)

    layers: dict[int, list[str]] = defaultdict(list)
    for node in nodes:
        layers[depth.get(node["id"], 0)].append(node["id"])

    max_rows = max((len(ids) for ids in layers.values()), default=1)
    positions: dict[str, dict[str, float]] = {}
    for d, ids in layers.items():
        offset = ((max_rows - len(ids)) * 140) / 2
        for i, nid in enumerate(ids):
            positions[nid] = {"x": 60 + d * 280, "y": 60 + offset + i * 140}

    for node in nodes:
        pos = positions.get(node["id"])
        if pos:
            node["position"] = pos
    return graph


# ---------------------------------------------------------------------------
# generate-workflow
# ---------------------------------------------------------------------------


def _draft_to_graph(draft: GeneratedWorkflowDraft) -> dict:
    """Convert a Gemini draft into canvas-shaped nodes/edges.

    Drops nodes with unknown node_type (and their edges), parses config_json
    defensively, and lays out positions.
    """
    valid_ids: set[str] = set()
    nodes: list[dict] = []
    for gen in draft.nodes:
        if gen.node_type not in NODE_TYPES_BY_ID:
            continue
        try:
            config = json.loads(gen.config_json) if gen.config_json else {}
            if not isinstance(config, dict):
                config = {}
        except (json.JSONDecodeError, TypeError):
            config = {}
        valid_ids.add(gen.id)
        nodes.append(
            {
                "id": gen.id,
                "type": "baseNode",
                "position": {"x": 0, "y": 0},
                "data": {"label": gen.label, "nodeType": gen.node_type, **config},
            }
        )

    edges: list[dict] = []
    seen_edges: set[str] = set()
    for gen in draft.edges:
        if gen.source not in valid_ids or gen.target not in valid_ids:
            continue
        edge_id = f"e-{gen.source}-{gen.target}"
        if edge_id in seen_edges:
            continue
        seen_edges.add(edge_id)
        edge: dict[str, Any] = {"id": edge_id, "source": gen.source, "target": gen.target}
        if gen.route:
            edge["data"] = {"route": gen.route}
        edges.append(edge)

    graph = {"nodes": nodes, "edges": edges}
    _assign_positions(graph)
    return graph


def generate_workflow(description: str) -> tuple[dict, list[str]]:
    base_prompt = (
        "You are an expert workflow architect for the Aegis agentic workflow builder. "
        "Design a workflow graph that fulfils the user's request using ONLY the node "
        "types below.\n\n"
        f"{_NODE_CATALOG}\n\n"
        f"{_GRAPH_RULES}\n\n"
        f"{_FEW_SHOT}\n\n"
        f"USER REQUEST:\n{description.strip()}\n\n"
        "Return a workflow draft. 'notes' must list everything the user still needs to "
        "configure before running (credentials, prompts, KB documents, integration "
        "targets, etc.)."
    )

    def _attempt(prompt: str) -> GeneratedWorkflowDraft:
        text = _generate_content(prompt, GeneratedWorkflowDraft, settings.assist_llm_timeout_seconds)
        return GeneratedWorkflowDraft.model_validate_json(text)

    draft = _attempt(base_prompt)
    graph = _draft_to_graph(draft)
    try:
        validate_workflow_graph(graph)
    except GraphValidationError as exc:
        retry_prompt = (
            f"{base_prompt}\n\n"
            f"Previous attempt failed validation: {exc}. Return a corrected workflow."
        )
        draft = _attempt(retry_prompt)
        graph = _draft_to_graph(draft)
        try:
            validate_workflow_graph(graph)
        except GraphValidationError as exc2:
            raise AssistError(
                f"The generated workflow failed validation twice: {exc2}"
            ) from exc2

    return graph, list(draft.notes)


# ---------------------------------------------------------------------------
# suggest-nodes
# ---------------------------------------------------------------------------

_SUGGEST_CACHE: dict[str, tuple[float, list[NodeSuggestion]]] = {}
_SUGGEST_CACHE_TTL = 300.0
_SUGGEST_CACHE_MAX = 256
_suggest_lock = Lock()


def _node_type_of(node: dict) -> str:
    return (node.get("data") or {}).get("nodeType", "")


def _graph_digest(graph: dict) -> str:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_sig = [(n.get("id"), _node_type_of(n)) for n in nodes]
    edge_sig = [
        (e.get("source"), e.get("target"), (e.get("data") or {}).get("route"))
        for e in edges
    ]
    payload = json.dumps([node_sig, edge_sig], sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _serialize_graph_compact(graph: dict, selected_node_id: str | None) -> str:
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    node_parts: list[str] = []
    selected_node: dict | None = None
    for node in nodes:
        node_id = node.get("id")
        data = node.get("data") or {}
        node_type = data.get("nodeType", "")
        label = data.get("label")
        if label:
            node_parts.append(f"{node_id}:{node_type}(label='{label}')")
        else:
            node_parts.append(f"{node_id}:{node_type}")
        if selected_node_id is not None and node_id == selected_node_id:
            selected_node = node

    edge_lines: list[str] = []
    for edge in edges:
        route = (edge.get("data") or {}).get("route")
        suffix = f"[{route}]" if route else ""
        edge_lines.append(f"{edge.get('source')}->{edge.get('target')}{suffix}")

    parts = ["NODES: " + ", ".join(node_parts), "EDGES:\n" + "\n".join(edge_lines)]

    if selected_node is not None:
        data = selected_node.get("data") or {}
        detail_bits: list[str] = []
        for key, value in data.items():
            if key in ("label", "nodeType"):
                continue
            sval = str(value)
            if len(sval) > 120:
                sval = sval[:120] + "…"
            detail_bits.append(f"{key}={sval}")
        parts.append(
            f"SELECTED NODE {selected_node_id}: " + ("; ".join(detail_bits) or "(no config)")
        )
    return "\n".join(parts)


def suggest_nodes(
    graph: dict,
    selected_node_id: str | None,
    user_id: str,
    history: list[AssistHistoryTurn] | None = None,
) -> list[NodeSuggestion]:
    digest = _graph_digest(graph)
    history_fragment = _history_cache_fragment(history)
    cache_key = hashlib.sha256(
        f"{user_id}|{selected_node_id}|{digest}|{history_fragment}".encode()
    ).hexdigest()

    now = time.monotonic()
    with _suggest_lock:
        cached = _SUGGEST_CACHE.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

    compact = _serialize_graph_compact(graph, selected_node_id)
    history_block = _format_history(history)
    history_segment = f"{history_block}\n\n" if history_block else ""
    prompt = (
        "You are a workflow copilot for the Aegis builder. Suggest up to 3 nodes to add "
        "next to improve or extend the workflow. Use ONLY these node types:\n\n"
        f"{_NODE_CATALOG}\n\n"
        "CURRENT WORKFLOW:\n"
        f"{compact}\n\n"
        + history_segment
        + (
            f"The user selected node '{selected_node_id}'; suggest nodes that would come after it.\n\n"
            if selected_node_id
            else ""
        )
        + "For each suggestion give node_type, a short label, and a one-sentence reason."
    )

    text = _generate_content(prompt, SuggestionsDraft, 12)
    draft = SuggestionsDraft.model_validate_json(text)

    suggestions: list[NodeSuggestion] = []
    for item in draft.suggestions:
        if item.node_type not in NODE_TYPES_BY_ID:
            continue
        suggestions.append(
            NodeSuggestion(
                node_type=item.node_type,
                label=item.label,
                reason=item.reason,
                default_data=None,
            )
        )
        if len(suggestions) >= 3:
            break

    with _suggest_lock:
        if len(_SUGGEST_CACHE) >= _SUGGEST_CACHE_MAX:
            # Evict the oldest (earliest-expiring) entry.
            oldest = min(_SUGGEST_CACHE, key=lambda k: _SUGGEST_CACHE[k][0])
            _SUGGEST_CACHE.pop(oldest, None)
        _SUGGEST_CACHE[cache_key] = (now + _SUGGEST_CACHE_TTL, suggestions)

    return suggestions


# ---------------------------------------------------------------------------
# explain-run
# ---------------------------------------------------------------------------

_EXPLAIN_CACHE: dict[str, ExplainRunResponse] = {}
_EXPLAIN_CACHE_MAX = 128
_explain_lock = Lock()


def _truncate(value: Any, limit: int) -> str:
    text = "" if value is None else str(value)
    if len(text) > limit:
        return text[:limit] + "…"
    return text


def explain_run(run: Any, graph: dict) -> ExplainRunResponse:
    run_key = str(run.id)
    with _explain_lock:
        cached = _EXPLAIN_CACHE.get(run_key)
    if cached is not None:
        return cached

    node_results = list(run.node_results or [])

    result_lines: list[str] = []
    for nr in node_results:
        is_failed = nr.status == "failed"
        limit = 4000 if is_failed else 300
        result_lines.append(
            f"- {nr.node_id} ({nr.node_type}, '{nr.node_label}'): status={nr.status}, "
            f"latency={nr.latency_ms}ms, output={_truncate(nr.output, limit)}"
        )

    node_sig = [
        (n.get("id"), _node_type_of(n)) for n in graph.get("nodes", [])
    ]
    edge_sig = [
        (e.get("source"), e.get("target"), (e.get("data") or {}).get("route"))
        for e in graph.get("edges", [])
    ]
    compact_graph = json.dumps({"nodes": node_sig, "edges": edge_sig}, default=str)

    prompt = (
        "You are debugging a failed workflow run in the Aegis builder. Explain what "
        "happened and why it failed, then suggest concrete fixes.\n\n"
        f"INPUT: {_truncate(run.input_text, 1000)}\n"
        f"FINAL OUTPUT: {_truncate(run.final_output, 1000)}\n\n"
        "NODE RESULTS (in order):\n" + "\n".join(result_lines) + "\n\n"
        f"GRAPH: {compact_graph}\n\n"
        "Write the explanation in short plain paragraphs and hyphen bullets. "
        "Do NOT use markdown headings and do NOT use code fences. "
        "Then provide suggested_fixes, each with a short title and a detail."
    )

    text = _generate_content(prompt, ExplainRunResponse, 30)
    result = ExplainRunResponse.model_validate_json(text)

    with _explain_lock:
        if len(_EXPLAIN_CACHE) >= _EXPLAIN_CACHE_MAX:
            _EXPLAIN_CACHE.pop(next(iter(_EXPLAIN_CACHE)), None)
        _EXPLAIN_CACHE[run_key] = result

    return result


# ---------------------------------------------------------------------------
# edit-graph (NL graph edit -> reviewable diff; never mutates stored workflow)
# ---------------------------------------------------------------------------


def _node_config(node: dict) -> dict:
    """Config subset of a node's data (excludes label/nodeType), for diffing."""
    data = node.get("data") or {}
    return {k: v for k, v in data.items() if k not in ("label", "nodeType")}


def _compute_graph_diff(current: dict, proposed: dict) -> GraphDiff:
    from app.schemas.assist import EdgeRef

    cur_nodes = {n.get("id"): n for n in current.get("nodes", []) if n.get("id")}
    prop_nodes = {n.get("id"): n for n in proposed.get("nodes", []) if n.get("id")}

    added_node_ids = [nid for nid in prop_nodes if nid not in cur_nodes]
    removed_node_ids = [nid for nid in cur_nodes if nid not in prop_nodes]
    changed_node_ids: list[str] = []
    for nid, prop_node in prop_nodes.items():
        cur_node = cur_nodes.get(nid)
        if cur_node is None:
            continue
        # A node changed if its type, label, or config differs (ignore position).
        cur_data = cur_node.get("data") or {}
        prop_data = prop_node.get("data") or {}
        if (
            cur_data.get("nodeType") != prop_data.get("nodeType")
            or cur_data.get("label") != prop_data.get("label")
            or _node_config(cur_node) != _node_config(prop_node)
        ):
            changed_node_ids.append(nid)

    def _edge_key(edge: dict) -> tuple[str, str, str | None]:
        route = (edge.get("data") or {}).get("route") or edge.get("label") or None
        return (edge.get("source"), edge.get("target"), route)

    cur_edges = {_edge_key(e): e for e in current.get("edges", [])}
    prop_edges = {_edge_key(e): e for e in proposed.get("edges", [])}

    added_edges = [
        EdgeRef(source=k[0], target=k[1], route=k[2])
        for k in prop_edges
        if k not in cur_edges
    ]
    removed_edges = [
        EdgeRef(source=k[0], target=k[1], route=k[2])
        for k in cur_edges
        if k not in prop_edges
    ]

    return GraphDiff(
        added_node_ids=added_node_ids,
        removed_node_ids=removed_node_ids,
        changed_node_ids=changed_node_ids,
        added_edges=added_edges,
        removed_edges=removed_edges,
    )


def edit_graph(
    graph: dict,
    instruction: str,
    history: list[AssistHistoryTurn] | None = None,
) -> EditGraphResponse:
    """Propose an NL edit to a graph, validated and returned as a diff.

    Never mutates the stored workflow — returns a proposal only. ``history``
    carries prior copilot turns so follow-up instructions resolve against
    earlier proposals; absent/empty history yields the original single-shot
    behaviour and an identical prompt.
    """
    compact = _serialize_graph_compact(graph, None)
    history_block = _format_history(history)
    history_segment = f"{history_block}\n\n" if history_block else ""
    base_prompt = (
        "You are an expert workflow editor for the Aegis agentic workflow builder. "
        "Apply the user's requested change to the CURRENT workflow and return the "
        "COMPLETE modified graph using ONLY the node types below. Preserve node ids "
        "that are unchanged so the edit can be diffed; only add/remove/modify nodes "
        "and edges as needed to satisfy the instruction.\n\n"
        f"{_NODE_CATALOG}\n\n"
        f"{_GRAPH_RULES}\n\n"
        f"{_FEW_SHOT}\n\n"
        f"CURRENT WORKFLOW:\n{compact}\n\n"
        f"{history_segment}"
        f"USER INSTRUCTION:\n{instruction.strip()}\n\n"
        "Return the full modified workflow (all nodes and edges, not just the delta). "
        "'summary' is a one-sentence description of what you changed; 'notes' lists "
        "anything the user still needs to configure."
    )

    def _attempt(prompt: str) -> tuple[dict, _EditGraphDraft]:
        text = _generate_content(prompt, _EditGraphDraft, settings.assist_llm_timeout_seconds)
        draft = _EditGraphDraft.model_validate_json(text)
        # Reuse the draft->graph converter (drops unknown node types, lays out).
        gen_draft = GeneratedWorkflowDraft(
            nodes=draft.nodes, edges=draft.edges, notes=draft.notes
        )
        proposed = _draft_to_graph(gen_draft)
        return proposed, draft

    proposed, draft = _attempt(base_prompt)
    try:
        validate_workflow_graph(proposed)
    except GraphValidationError as exc:
        retry_prompt = (
            f"{base_prompt}\n\n"
            f"Previous attempt failed validation: {exc}. Return a corrected workflow."
        )
        proposed, draft = _attempt(retry_prompt)
        try:
            validate_workflow_graph(proposed)
        except GraphValidationError as exc2:
            raise AssistError(
                f"The edited workflow failed validation twice: {exc2}"
            ) from exc2

    diff = _compute_graph_diff(graph, proposed)
    return EditGraphResponse(
        proposed_graph=proposed,
        diff=diff,
        notes=list(draft.notes),
        summary=draft.summary or "",
    )


# ---------------------------------------------------------------------------
# compare (run 2-3 variants of one LLM node over a single sample)
# ---------------------------------------------------------------------------


def _single_node_graph(node_type: str, config: dict) -> dict:
    """Wrap a single node between a trigger and end for single-node execution."""
    return {
        "nodes": [
            {
                "id": "trigger",
                "type": "baseNode",
                "position": {"x": 0, "y": 0},
                "data": {"label": "Trigger", "nodeType": "trigger", "triggerType": "manual"},
            },
            {
                "id": "node",
                "type": "baseNode",
                "position": {"x": 280, "y": 0},
                "data": {"label": "Variant", "nodeType": node_type, **(config or {})},
            },
            {
                "id": "end",
                "type": "baseNode",
                "position": {"x": 560, "y": 0},
                "data": {"label": "End", "nodeType": "end"},
            },
        ],
        "edges": [
            {"id": "e-trigger-node", "source": "trigger", "target": "node"},
            {"id": "e-node-end", "source": "node", "target": "end"},
        ],
    }


async def _run_single_node_variant(
    node_type: str, config: dict, input_text: str
) -> CompareVariantResult:
    """Execute one variant as a single-node LLM run, capturing telemetry.

    Reuses the compiler + ADK Runner + TokenTrackerPlugin execution path used by
    the executor, but in-memory (no DB persistence).
    """
    import uuid as _uuid

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    from app.services.compiler import compile_workflow
    from app.services.token_tracker import TokenTrackerPlugin
    from app.services.workflow_context import WorkflowContext

    graph = _single_node_graph(node_type, config)
    workflow_context = WorkflowContext.from_input(input_text)
    context_ref = workflow_context.to_dict()

    try:
        workflow, metadata, author_lookup = compile_workflow(graph, context_ref=context_ref)
    except Exception as exc:  # noqa: BLE001 — bad config -> report per-variant
        return CompareVariantResult(label="", error=f"Compile failed: {exc}")

    token_tracker = TokenTrackerPlugin(capture_calls=False)
    runner = Runner(
        app_name="aegis",
        node=workflow,
        session_service=InMemorySessionService(),
        auto_create_session=True,
        plugins=[token_tracker],
    )

    start = time.monotonic()
    output: str | None = None
    try:
        async for event in runner.run_async(
            user_id="aegis-compare",
            session_id=str(_uuid.uuid4()),
            new_message=types.Content(parts=[types.Part(text=input_text)]),
        ):
            author = getattr(event, "author", None) or "workflow"
            node_path = getattr(getattr(event, "node_info", None), "path", None)
            from app.services.executor import _extract_text_from_event, _resolve_node_id

            matched = _resolve_node_id(author, metadata, author_lookup, node_path)
            if matched != "node":
                continue
            text = _extract_text_from_event(event)
            if text:
                output = text
    except Exception as exc:  # noqa: BLE001 — model/transport failure per-variant
        latency_ms = int((time.monotonic() - start) * 1000)
        return CompareVariantResult(label="", latency_ms=latency_ms, error=str(exc))

    latency_ms = int((time.monotonic() - start) * 1000)

    total_tokens: int | None = None
    cost_usd: float | None = None
    if token_tracker.usage_by_agent:
        rows = token_tracker.usage_with_cost(settings.gemini_model)
        tokens_sum = sum(int(r.get("total_tokens") or 0) for r in rows.values())
        total_tokens = tokens_sum or None
        costs = [r["cost_usd"] for r in rows.values() if r.get("cost_usd") is not None]
        cost_usd = round(sum(costs), 6) if costs else None

    return CompareVariantResult(
        label="",
        output=output,
        latency_ms=latency_ms,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
    )


async def compare_variants(payload: CompareRequest) -> list[CompareVariantResult]:
    """Run each variant (base_config merged with overrides) as a single-node run.

    Graceful degrade when no API key: returns a per-variant error (HTTP 200).
    """
    results: list[CompareVariantResult] = []
    for variant in payload.variants:
        merged = {**(payload.base_config or {}), **(variant.config_overrides or {})}
        if not settings.google_api_key:
            results.append(
                CompareVariantResult(
                    label=variant.label,
                    error="GOOGLE_API_KEY is not configured. Add it to .env to compare variants.",
                )
            )
            continue
        try:
            result = await _run_single_node_variant(
                payload.node_type, merged, payload.input_text
            )
        except Exception as exc:  # noqa: BLE001 — never fail the whole request
            result = CompareVariantResult(label=variant.label, error=str(exc))
        result.label = variant.label
        results.append(result)
    return results


# ---------------------------------------------------------------------------
# generate-schema (magic-wand NL -> JSON Schema / regex)
# ---------------------------------------------------------------------------


def generate_schema(description: str, kind: str) -> GenerateSchemaResponse:
    kind = (kind or "json_schema").lower()
    if kind not in ("json_schema", "regex"):
        raise AssistError(f"Unsupported kind: {kind!r} (expected 'json_schema' or 'regex').")

    if kind == "regex":
        prompt = (
            "You are a regex expert. Produce a single regular expression (Python "
            "`re` syntax) that matches the described text. Return ONLY the regex "
            "string in the 'regex' field (no delimiters, no flags), leave "
            "'schema_json' null, and add any caveats to 'notes'.\n\n"
            f"DESCRIPTION:\n{description.strip()}"
        )
    else:
        prompt = (
            "You are a JSON Schema expert. Produce a valid JSON Schema (draft 2020-12) "
            "object describing the data the user described. Return the schema as a "
            "JSON-encoded string in the 'schema_object_json' field (e.g. "
            '"{\\"type\\": \\"object\\", ...}"), leave \'regex\' null, and add any '
            "assumptions to 'notes'.\n\n"
            f"DESCRIPTION:\n{description.strip()}"
        )

    text = _generate_content(prompt, _GeneratedSchemaDraft, settings.assist_llm_timeout_seconds)
    draft = _GeneratedSchemaDraft.model_validate_json(text)

    if kind == "regex":
        regex = (draft.regex or "").strip()
        if not regex:
            raise AssistError("The model did not return a usable regex.")
        # Reject catastrophic-backtracking / unsafe patterns before returning.
        try:
            from app.services.regex_safety import validate_safe_regex

            validate_safe_regex(regex)
        except Exception as exc:  # noqa: BLE001 — surface as an assist error
            raise AssistError(f"The generated regex was rejected as unsafe: {exc}") from exc
        return GenerateSchemaResponse(regex=regex, notes=list(draft.notes))

    parsed: Any
    try:
        parsed = json.loads(draft.schema_object_json) if draft.schema_object_json else None
    except (json.JSONDecodeError, TypeError) as exc:
        raise AssistError("The model returned an unparseable JSON Schema.") from exc
    if not isinstance(parsed, dict):
        raise AssistError("The model did not return a JSON Schema object.")
    return GenerateSchemaResponse(json_schema=parsed, notes=list(draft.notes))


# ---------------------------------------------------------------------------
# Rate limiting (per-user, in-memory, always on)
# ---------------------------------------------------------------------------

_rate_lock = Lock()
_rate_buckets: dict[str, list[float]] = defaultdict(list)

_ENDPOINT_LIMITS = {
    "generate": "assist_generate_per_minute",
    "suggest": "assist_suggest_per_minute",
    "explain": "assist_explain_per_minute",
    "edit": "assist_edit_per_minute",
    "compare": "assist_compare_per_minute",
    "schema": "assist_schema_per_minute",
}


def check_assist_rate_limit(user_id: str, endpoint: str) -> None:
    limit = int(getattr(settings, _ENDPOINT_LIMITS[endpoint]))
    window_seconds = 60.0
    now = time.monotonic()
    key = f"{user_id}:{endpoint}"
    with _rate_lock:
        recent = [ts for ts in _rate_buckets[key] if now - ts < window_seconds]
        if len(recent) >= limit:
            _rate_buckets[key] = recent
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded ({limit} requests per minute)",
            )
        recent.append(now)
        _rate_buckets[key] = recent
