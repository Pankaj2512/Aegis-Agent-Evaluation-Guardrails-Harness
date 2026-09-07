from __future__ import annotations

import ast
import asyncio
import hashlib
import json
import operator
import re
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from google.adk import Agent, Workflow
from google.adk.tools.google_search_tool import google_search
from google.genai import types
from google.adk.workflow import Edge as AdkEdge
from google.adk.workflow import JoinNode, START
from google.adk.workflow._graph import DEFAULT_ROUTE
from google.adk.workflow import node as workflow_node
from google.adk.workflow._base_node import BaseNode
from app.config import settings
from app.services.context_wrapper import SUCCESS_ROUTE, wrap_with_context
from app.services.eval import EvalScores, build_eval_instruction
from app.services.expressions import render_template, template_uses_expressions
from app.services.graph_validation import validate_workflow_graph
from app.services.guardrail import GuardrailResult, apply_fail_behavior, validate_guardrail_content
from app.services.node_handlers import (
    filter_executable_graph,
    is_annotation_node,
    _make_code_fn,
    _make_delay_fn,
    _make_filter_fn,
    _make_http_fn,
    _make_human_approval_fn,
    _make_integration_fn,
    _make_sub_workflow_fn,
    _make_if_fn,
    _make_input_schema_fn,
    _make_iteration_fn,
    _make_json_parse_fn,
    _make_kb_retrieve_fn,
    _make_memory_retrieve_fn,
    _make_memory_store_fn,
    _make_set_fields_fn,
    _make_switch_fn,
    _make_transform_fn,
)
from app.services.routing_models import ClassifierDecision, RouterDecision
from app.services.search import run_search

MAX_EXPRESSION_LENGTH = 200
MAX_ABS_OPERAND = 1_000_000
MAX_POW_EXPONENT = 100

SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _safe_eval(expression: str) -> str:
    expression = expression.strip()
    if not expression:
        return "0"
    if len(expression) > MAX_EXPRESSION_LENGTH:
        return f"Calculator error: expression exceeds {MAX_EXPRESSION_LENGTH} characters"
    try:
        node = ast.parse(expression, mode="eval")
        return str(_eval_node(node.body))
    except Exception as exc:
        return f"Calculator error: {exc}"


def _guard_operand(value: float) -> float:
    if abs(value) > MAX_ABS_OPERAND:
        raise ValueError(f"operand exceeds limit of {MAX_ABS_OPERAND}")
    return value


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return _guard_operand(float(node.value))
    if isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPERATORS:
        if isinstance(node.op, ast.Pow):
            exponent = _eval_node(node.right)
            if abs(exponent) > MAX_POW_EXPONENT:
                raise ValueError(f"exponent exceeds limit of {MAX_POW_EXPONENT}")
            base = _eval_node(node.left)
            return float(SAFE_OPERATORS[type(node.op)](base, exponent))
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return float(SAFE_OPERATORS[type(node.op)](left, right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_OPERATORS:
        return float(SAFE_OPERATORS[type(node.op)](_eval_node(node.operand)))
    raise ValueError("Unsupported expression")


def topological_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
    node_ids = {n["id"] for n in nodes}
    indegree: dict[str, int] = {nid: 0 for nid in node_ids}
    adjacency: dict[str, list[str]] = defaultdict(list)

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source in node_ids and target in node_ids:
            adjacency[source].append(target)
            indegree[target] += 1

    from collections import deque

    queue: deque[str] = deque([nid for nid, deg in indegree.items() if deg == 0])
    order: list[str] = []

    while queue:
        current = queue.popleft()
        order.append(current)
        for neighbor in adjacency[current]:
            indegree[neighbor] -= 1
            if indegree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(node_ids):
        raise ValueError("Workflow graph must be a directed acyclic graph (no cycles).")

    return order


def _node_data(node: dict) -> dict:
    return node.get("data", {}) or {}


def _safe_float(value: Any, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_adk_name(node_id: str, prefix: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_]", "_", node_id)
    if safe and safe[0].isdigit():
        safe = f"n_{safe}"
    return f"{prefix}_{safe}"


def _make_passthrough_fn(node_id: str, prefix: str) -> Callable[[str], str]:
    def passthrough(node_input: str) -> str:
        return str(node_input)

    passthrough.__name__ = _safe_adk_name(node_id, prefix)
    return passthrough


def _make_expression_agent_fn(
    node_id: str,
    instruction_template: str,
    context_ref: dict[str, Any],
    adk_name: str,
) -> Callable[[str], Any]:
    async def agent(node_input: str) -> str:
        rendered = render_template(instruction_template, context_ref, str(node_input))

        def _call() -> str:
            from google import genai

            client = genai.Client(api_key=settings.google_api_key)
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=str(node_input),
                config=types.GenerateContentConfig(system_instruction=rendered),
            )
            return response.text or ""

        return await asyncio.to_thread(_call)

    agent.__name__ = adk_name
    return agent


def _make_llm_decision_fn(
    node_id: str,
    instruction: str,
    schema: type,
    adk_name: str,
) -> Callable[[str], Any]:
    """LLM router/classifier as a function node.

    ADK 2.x ignores routes returned via Agent output_schema, so decisions are
    made with a direct model call and returned as a decision object — the
    context wrapper translates it into ctx.route.
    """

    async def decide(node_input: str) -> Any:
        def _call() -> Any:
            from google import genai

            client = genai.Client(api_key=settings.google_api_key)
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=str(node_input)[:8000],
                config=types.GenerateContentConfig(
                    system_instruction=instruction,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )
            return schema.model_validate_json(response.text or "{}")

        return await asyncio.to_thread(_call)

    decide.__name__ = adk_name
    return decide


def _make_calculator_fn(node_id: str) -> Callable[[str], str]:
    def calculator(node_input: str) -> str:
        return _safe_eval(str(node_input))

    calculator.__name__ = _safe_adk_name(node_id, "calculator")
    return calculator


def _google_search_generate_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        tool_config=types.ToolConfig(
            include_server_side_tool_invocations=True,
        ),
    )


def _make_search_fn(node_id: str, provider: str) -> Callable[[str], Any]:
    async def search_tool(node_input: str) -> str:
        if provider == "google":
            return str(node_input)
        return await run_search(provider, str(node_input))

    search_tool.__name__ = _safe_adk_name(node_id, "search")
    return search_tool


def _make_guardrail_fn(
    node_id: str,
    rules: dict[str, Any],
    on_result: Callable[[str, GuardrailResult], None] | None = None,
) -> Callable[[str], str | RouterDecision]:
    fail_behavior = rules.get("fail_behavior", "block")
    pass_route = str(rules.get("pass_route") or "pass")
    failure_route = str(rules.get("failure_route") or "failed")

    def guardrail(node_input: str) -> str | RouterDecision:
        text = str(node_input)
        result = validate_guardrail_content(text, rules)
        if fail_behavior == "route":
            route = pass_route if result.passed else failure_route
            if on_result:
                on_result(node_id, result)
            return RouterDecision(route=route, reasoning=result.message)

        try:
            result = apply_fail_behavior(
                result,
                fail_behavior,
                node_id,
                content=text,
                rules=rules,
            )
        except Exception:
            if on_result:
                on_result(node_id, result)
            raise
        if on_result:
            on_result(node_id, result)
        if result.output_override is not None:
            return result.output_override
        return text

    guardrail.__name__ = _safe_adk_name(node_id, "guardrail")
    return guardrail


def _build_adk_node(
    node: dict,
    on_guardrail_result: Callable[[str, GuardrailResult], None] | None,
    context_ref: dict[str, Any] | None = None,
) -> Any:
    node_id = node["id"]
    data = _node_data(node)
    node_type = data.get("nodeType", "agent")
    label = data.get("label", node_type)

    if node_type == "agent":
        instruction = data.get(
            "instruction",
            "You are a helpful AI assistant. Respond clearly and concisely to the user input.",
        )
        if context_ref is not None and template_uses_expressions(instruction):
            return _make_expression_agent_fn(
                node_id,
                instruction,
                context_ref,
                _safe_adk_name(node_id, "agent"),
            )
        return Agent(
            name=_safe_adk_name(node_id, "agent"),
            model=settings.gemini_model,
            instruction=instruction,
            output_schema=str,
        )

    if node_type == "router":
        routes = data.get("routes") or ["default"]
        route_list = ", ".join(f'"{r}"' for r in routes)
        return _make_llm_decision_fn(
            node_id,
            (
                f"Analyze the input and choose exactly one route from: {route_list}. "
                "Return the route key and brief reasoning."
            ),
            RouterDecision,
            _safe_adk_name(node_id, "router"),
        )

    if node_type == "classifier":
        categories = data.get("categories") or ["default"]
        cat_list = ", ".join(f'"{c}"' for c in categories)
        return _make_llm_decision_fn(
            node_id,
            (
                f"Classify the input into exactly one category from: {cat_list}. "
                "Return the category key and brief reasoning."
            ),
            ClassifierDecision,
            _safe_adk_name(node_id, "classifier"),
        )

    if node_type == "summarizer":
        style = data.get("summaryStyle", "concise")
        return Agent(
            name=_safe_adk_name(node_id, "summarizer"),
            model=settings.gemini_model,
            instruction=(
                f"Summarize the following content in a {style} style. "
                "Preserve key facts. Return only the summary."
            ),
            output_schema=str,
        )

    if node_type == "translator":
        target_lang = data.get("targetLanguage", "English")
        return Agent(
            name=_safe_adk_name(node_id, "translator"),
            model=settings.gemini_model,
            instruction=(
                f"Translate the following text to {target_lang}. "
                "Preserve meaning and tone. Return only the translation."
            ),
            output_schema=str,
        )

    if node_type == "extractor":
        fields = data.get("extractFields") or ["summary", "entities"]
        field_list = ", ".join(fields)
        return Agent(
            name=_safe_adk_name(node_id, "extractor"),
            model=settings.gemini_model,
            instruction=(
                f"Extract these fields from the input as JSON: {field_list}. "
                "Return valid JSON only with the requested keys."
            ),
            output_schema=str,
        )

    if node_type == "transform":
        return _make_transform_fn(
            node_id,
            data.get("template", "{{input}}"),
            _safe_adk_name(node_id, "transform"),
            context_ref,
        )

    if node_type == "json_parse":
        return _make_json_parse_fn(
            node_id,
            data.get("jsonPath"),
            _safe_adk_name(node_id, "json_parse"),
        )

    if node_type == "delay":
        return _make_delay_fn(
            node_id,
            _safe_float(data.get("delaySeconds"), 1.0),
            _safe_adk_name(node_id, "delay"),
        )

    if node_type == "note":
        raise ValueError("Annotation nodes are not compiled")

    if node_type == "trigger":
        return _make_passthrough_fn(node_id, "trigger")

    if node_type == "end":
        return _make_passthrough_fn(node_id, "end")

    if node_type == "join":
        return JoinNode(name=_safe_adk_name(node_id, "join"))

    if node_type == "input_schema":
        return _make_input_schema_fn(
            node_id,
            data.get("inputFields") or [],
            _safe_adk_name(node_id, "input_schema"),
            context_ref,
        )

    if node_type == "set_fields":
        field_map = data.get("setFields") or {}
        if isinstance(field_map, list):
            field_map = {
                item["key"]: item["value"]
                for item in field_map
                if isinstance(item, dict) and item.get("key")
            }
        return _make_set_fields_fn(
            node_id,
            field_map,
            _safe_adk_name(node_id, "set_fields"),
            context_ref,
        )

    if node_type == "filter":
        cond = data.get("filterCondition") or {}
        return _make_filter_fn(
            node_id,
            cond.get("left", "{{last_output}}"),
            cond.get("operator", "not_empty"),
            cond.get("right"),
            _safe_adk_name(node_id, "filter"),
            context_ref,
        )

    if node_type == "if":
        cond = data.get("ifCondition") or {}
        return _make_if_fn(
            node_id,
            cond.get("left", "{{last_output}}"),
            cond.get("operator", "not_empty"),
            cond.get("right"),
            _safe_adk_name(node_id, "if"),
            context_ref,
        )

    if node_type == "switch":
        return _make_switch_fn(
            node_id,
            data.get("switchValue", "{{last_output}}"),
            data.get("switchCases") or [],
            data.get("switchDefault", "default"),
            _safe_adk_name(node_id, "switch"),
            context_ref,
        )

    if node_type == "code":
        return _make_code_fn(
            node_id,
            data.get("code", "result = last_output"),
            _safe_adk_name(node_id, "code"),
            context_ref,
        )

    if node_type == "memory_store":
        return _make_memory_store_fn(
            node_id,
            data.get("memoryNamespace", "default"),
            data.get("memoryKey", "{{input.text}}"),
            data.get("memoryValue", "{{last_output}}"),
            _safe_adk_name(node_id, "memory_store"),
            context_ref,
            persistent=bool(data.get("memoryPersistent")),
        )

    if node_type == "memory_retrieve":
        return _make_memory_retrieve_fn(
            node_id,
            data.get("memoryNamespace", "default"),
            data.get("memoryKey", "{{input.text}}"),
            _safe_adk_name(node_id, "memory_retrieve"),
            context_ref,
        )

    if node_type == "kb_retrieve":
        docs = data.get("kbDocuments") or []
        if isinstance(docs, str):
            try:
                docs = json.loads(docs)
            except json.JSONDecodeError:
                docs = []
        return _make_kb_retrieve_fn(
            node_id,
            data.get("kbQuery", "{{last_output}}"),
            docs if isinstance(docs, list) else [],
            max(1, _safe_int(data.get("kbTopK"), 3)),
            _safe_adk_name(node_id, "kb_retrieve"),
            context_ref,
            kb_source=data.get("kbSource", "inline"),
            retrieval_method=data.get("kbMethod", "bm25"),
        )

    if node_type == "human_approval":
        return _make_human_approval_fn(
            node_id,
            data.get("approvalReview", "{{last_output}}"),
            _safe_adk_name(node_id, "human_approval"),
            context_ref,
        )

    if node_type == "integration":
        return _make_integration_fn(
            node_id,
            data.get("integrationType", "slack"),
            data.get("credentialId"),
            data.get("credentialName"),
            data.get("integrationMessage"),
            data.get("integrationSubject"),
            data.get("integrationBody"),
            data.get("integrationQuery"),
            _safe_adk_name(node_id, "integration"),
            context_ref,
        )

    if node_type == "sub_workflow":
        return _make_sub_workflow_fn(
            node_id,
            data.get("subWorkflowId"),
            data.get("subWorkflowInput", "{{last_output}}"),
            _safe_adk_name(node_id, "sub_workflow"),
            context_ref,
        )

    if node_type == "iteration":
        return _make_iteration_fn(
            node_id,
            data.get("itemsExpression", "{{last_output}}"),
            data.get("itemTemplate", "{{item}}"),
            data.get("subWorkflowId"),
            data.get("iterationMode", "sequential"),
            _safe_int(data.get("maxItems"), 25),
            data.get("onItemError", "fail"),
            _safe_adk_name(node_id, "iteration"),
            context_ref,
        )

    if node_type == "tool":
        tool_kind = data.get("toolType", "calculator")
        if tool_kind == "calculator":
            return _make_calculator_fn(node_id)
        if tool_kind == "http":
            headers = data.get("httpHeaders") or {}
            if isinstance(headers, list):
                headers = {}
            return _make_http_fn(
                node_id,
                data.get("httpMethod", "GET"),
                data.get("httpUrl", ""),
                headers,
                data.get("httpBody"),
                _safe_adk_name(node_id, "http"),
                context_ref,
            )
        provider = data.get("searchProvider", "google")
        if provider == "google":
            return Agent(
                name=_safe_adk_name(node_id, "search"),
                model=settings.gemini_model,
                instruction=(
                    "Search for information about the user's query and return a concise, "
                    "factual summary with key findings. Return only the summary."
                ),
                tools=[google_search],
                generate_content_config=_google_search_generate_config(),
                output_schema=str,
            )
        return _make_search_fn(node_id, provider)

    if node_type == "evaluation":
        preset = data.get("evalPreset")
        criteria = data.get("criteria")
        eval_type = (data.get("evalType") or "llm").lower()
        eval_mode = (data.get("evalExecutionMode") or "parallel").lower()
        use_inline = eval_mode == "inline" and eval_type == "llm"
        if use_inline:
            instruction = data.get("evalInstruction") or build_eval_instruction(preset, criteria)
            # Nodes are rebuilt per run with the live context_ref, so the run
            # input is available here; judging against the original request
            # keeps relevance/helpfulness scores meaningful.
            request_text = ""
            if context_ref is not None:
                request_text = str((context_ref.get("input") or {}).get("text") or "")
            if request_text:
                instruction += (
                    f"\n\nThe original user request was:\n{request_text[:4000]}\n\n"
                    "Judge the content as a response to that request."
                )
            return Agent(
                name=_safe_adk_name(node_id, "eval"),
                model=settings.gemini_model,
                instruction=instruction,
                output_schema=EvalScores,
            )
        return _make_passthrough_fn(node_id, "eval")

    if node_type == "guardrail":
        rules = data.get("rules", {})
        return _make_guardrail_fn(node_id, rules, on_guardrail_result)

    raise ValueError(f"Unsupported node type: {node_type}")


def _ensure_base_node(adk_node: Any) -> BaseNode:
    if isinstance(adk_node, BaseNode):
        return adk_node
    if callable(adk_node):
        return workflow_node(adk_node)
    raise ValueError(f"Cannot convert {type(adk_node)} to ADK node")


def _branch_default_label(node: dict) -> str | None:
    """Return the label of the fallback/default route for a branching node.

    Edges from a branch node carrying this label must be tagged with ADK's
    DEFAULT_ROUTE sentinel (fire only when no specific route matched), NOT
    route=None (which ADK treats as unconditional — firing alongside the
    matched branch). Non-branch nodes have no default route.
    """
    data = _node_data(node)
    node_type = data.get("nodeType")
    if node_type == "switch":
        return str(data.get("switchDefault", "default"))
    # router/classifier/if/guardrail-route emit only explicit routes; a raw
    # "default"-labelled edge on them is still a fallback sentinel in ADK terms.
    if node_type in {"router", "classifier"}:
        return "default"
    return None


def _edge_route(edge: dict, default_label: str | None = None) -> str | None:
    data = edge.get("data") or {}
    route = data.get("route") or edge.get("label")
    if route in (None, ""):
        return None
    route = str(route)
    if default_label is not None and route == default_label:
        return DEFAULT_ROUTE
    # An edge leaving a non-branch node labelled "default" is unconditional.
    if default_label is None and route == "default":
        return None
    return route


def _error_edge_sources(edges: list[dict]) -> set[str]:
    """IDs of nodes that carry an outgoing error edge (data.route == "error")."""
    return {
        e["source"]
        for e in edges
        if e.get("source") and str((e.get("data") or {}).get("route") or "") == "error"
    }


def _build_graph_edges(
    nodes: list[dict],
    edges: list[dict],
    adk_nodes: dict[str, Any],
    summary: dict,
) -> list[AdkEdge]:
    node_ids = {n["id"] for n in nodes}
    indegree: dict[str, int] = {nid: 0 for nid in node_ids}
    node_type_map = {n["id"]: _node_data(n).get("nodeType") for n in nodes}
    default_label_map: dict[str, str | None] = {
        n["id"]: _branch_default_label(n) for n in nodes
    }
    error_guarded = _error_edge_sources(edges)

    for edge in edges:
        target = edge.get("target")
        if target in indegree:
            indegree[target] += 1

    # No implicit all-predecessor joins: exclusive branches (if/switch/router/
    # classifier/guardrail-route) merge on first arrival — an auto JoinNode
    # would wait for branches that never ran and deadlock the tail of the
    # graph. True parallel fan-in uses the explicit Join node type.
    join_redirect: dict[str, str] = {}

    adk_edges: list[AdkEdge] = []
    entry = summary["entry_node"]
    adk_edges.append(AdkEdge(from_node=START, to_node=adk_nodes[entry]))

    for edge in edges:
        source = edge["source"]
        target = edge["target"]
        route = _edge_route(edge, default_label_map.get(source))
        # A node with an error edge needs its success edges to be conditional so
        # they do not fire on the error path. Unconditional (route=None) success
        # edges are stamped with the SUCCESS_ROUTE sentinel; the wrapper emits
        # that route on success. Already-routed edges (branch nodes, the error
        # edge itself) are left as-is.
        if source in error_guarded and route is None:
            route = SUCCESS_ROUTE
        resolved_target = join_redirect.get(target, target)
        adk_edges.append(
            AdkEdge(
                from_node=adk_nodes[source],
                to_node=adk_nodes[resolved_target],
                route=route,
            )
        )

    for target, join_key in join_redirect.items():
        adk_edges.append(AdkEdge(from_node=adk_nodes[join_key], to_node=adk_nodes[target]))

    return adk_edges


_MAX_COMPILE_CACHE = 32
_CompileCacheEntry = tuple[dict, dict, dict[str, dict], dict[str, str]]
_compile_cache: dict[str, _CompileCacheEntry] = {}


def _graph_cache_key(graph_json: dict) -> str:
    payload = json.dumps(graph_json, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def _graph_has_guardrail(graph_json: dict) -> bool:
    for node in graph_json.get("nodes", []):
        if (_node_data(node).get("nodeType")) == "guardrail":
            return True
    return False


def _build_author_lookup(metadata: dict[str, dict]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for node_id, meta in metadata.items():
        if meta.get("is_annotation"):
            continue
        adk_name = meta.get("adk_name")
        if adk_name:
            lookup[adk_name] = node_id
        lookup[node_id] = node_id
    return lookup


def clear_compile_cache() -> None:
    _compile_cache.clear()


def _populate_node_metadata(metadata: dict[str, dict], node: dict, adk_name: str) -> None:
    node_id = node["id"]
    data = _node_data(node)
    node_type = data.get("nodeType", "agent")
    label = data.get("label", node_type)
    metadata[node_id] = {
        "type": node_type,
        "label": label,
        "adk_name": adk_name,
        "node_id": node_id,
    }

    if node_type == "evaluation":
        eval_type = (data.get("evalType") or "llm").lower()
        eval_mode = (data.get("evalExecutionMode") or "parallel").lower()
        metadata[node_id]["is_evaluation"] = True
        metadata[node_id]["eval_type"] = eval_type
        metadata[node_id]["eval_preset"] = data.get("evalPreset")
        metadata[node_id]["custom_preset_id"] = data.get("evalCustomPresetId")
        metadata[node_id]["criteria"] = data.get("criteria")
        metadata[node_id]["eval_instruction"] = data.get("evalInstruction")
        metadata[node_id]["score_weights"] = data.get("scoreWeights")
        metadata[node_id]["eval_expected"] = data.get("evalExpected")
        metadata[node_id]["eval_pattern"] = data.get("evalPattern")
        metadata[node_id]["eval_baseline"] = data.get("evalBaseline")
        threshold = data.get("evalSimilarityThreshold")
        if isinstance(threshold, (int, float)):
            metadata[node_id]["eval_similarity_threshold"] = float(threshold)
        metadata[node_id]["eval_deferred"] = eval_type != "llm" or eval_mode != "inline"
        metadata[node_id]["eval_execution_mode"] = eval_mode
        threshold = data.get("evalThreshold")
        if isinstance(threshold, (int, float)):
            metadata[node_id]["eval_threshold"] = float(threshold)
        # Numeric eval strategy (eval_deterministic.evaluate_numeric) reads this.
        metadata[node_id]["eval_tolerance"] = _safe_float(data.get("evalTolerance"), 0.0)
        fail_behavior = data.get("evalFailBehavior") or "none"
        metadata[node_id]["eval_fail_behavior"] = fail_behavior
    if node_type == "guardrail":
        metadata[node_id]["is_guardrail"] = True
        rules = data.get("rules", {})
        metadata[node_id]["guardrail_mode"] = rules.get("mode", "output")
        metadata[node_id]["guardrail_type"] = rules.get("guardrail_type", "rules")
        metadata[node_id]["fail_behavior"] = rules.get("fail_behavior", "block")
        if rules.get("fail_behavior") == "route":
            metadata[node_id]["is_branch"] = True
            metadata[node_id]["routes"] = [
                str(rules.get("pass_route") or "pass"),
                str(rules.get("failure_route") or "failed"),
            ]
    if node_type == "router":
        metadata[node_id]["is_router"] = True
        metadata[node_id]["routes"] = data.get("routes", [])
    if node_type == "if":
        metadata[node_id]["is_branch"] = True
        metadata[node_id]["routes"] = ["true", "false"]
    if node_type == "switch":
        metadata[node_id]["is_branch"] = True
        cases = list(data.get("switchCases") or [])
        default_route = data.get("switchDefault", "default")
        metadata[node_id]["routes"] = [*cases, default_route]
    if node_type == "classifier":
        metadata[node_id]["is_classifier"] = True
        metadata[node_id]["categories"] = data.get("categories", [])
    if node_type == "join":
        metadata[node_id]["is_join"] = True
    if node_type == "trigger":
        metadata[node_id]["is_trigger"] = True
        metadata[node_id]["trigger_type"] = data.get("triggerType", "manual")
    if node_type == "end":
        metadata[node_id]["is_end"] = True
    if node_type == "human_approval":
        metadata[node_id]["is_human_approval"] = True
    if node_type == "tool" and data.get("toolType") == "search":
        metadata[node_id]["searchProvider"] = data.get("searchProvider", "google")


def _build_bound_workflow(
    graph_json: dict,
    summary: dict,
    executable: dict,
    metadata: dict[str, dict],
    *,
    on_guardrail_result: Callable[[str, GuardrailResult], None] | None = None,
    context_ref: dict[str, Any] | None = None,
) -> Workflow:
    nodes: list[dict] = executable.get("nodes", [])
    edges: list[dict] = executable.get("edges", [])
    adk_nodes: dict[str, Any] = {}
    error_guarded = _error_edge_sources(edges)

    for node in graph_json.get("nodes", []):
        node_id = node["id"]
        data = _node_data(node)
        node_type = data.get("nodeType", "agent")
        label = data.get("label", node_type)

        if is_annotation_node(node_type):
            continue

        built = _build_adk_node(node, on_guardrail_result, context_ref)
        if context_ref is not None and callable(built) and not isinstance(built, (Agent, JoinNode, BaseNode)):
            built = wrap_with_context(
                node_id,
                built,
                context_ref,
                label=label,
                node_type=node_type,
                retries=max(0, _safe_int(data.get("retries"), 0)),
                retry_delay_sec=_safe_float(data.get("retryDelaySec"), 1.0),
                timeout_sec=(_safe_float(data.get("timeoutSec"), 0.0) or None) if data.get("timeoutSec") else None,
                error_branch=node_id in error_guarded,
            )
        adk_nodes[node_id] = _ensure_base_node(built)

    adk_edges = _build_graph_edges(nodes, edges, adk_nodes, summary)
    return Workflow(name="aegis_workflow", edges=adk_edges)


def compile_workflow(
    graph_json: dict,
    on_guardrail_result: Callable[[str, GuardrailResult], None] | None = None,
    context_ref: dict[str, Any] | None = None,
) -> tuple[Workflow, dict[str, dict], dict[str, str]]:
    cache_key = _graph_cache_key(graph_json)
    cached = _compile_cache.get(cache_key)
    if cached:
        summary, executable, metadata, author_lookup = cached
        workflow = _build_bound_workflow(
            graph_json,
            summary,
            executable,
            metadata,
            on_guardrail_result=on_guardrail_result,
            context_ref=context_ref,
        )
        return workflow, metadata, author_lookup

    summary = validate_workflow_graph(graph_json)
    executable = filter_executable_graph(graph_json)
    metadata: dict[str, dict] = {}

    for node in graph_json.get("nodes", []):
        node_id = node["id"]
        data = _node_data(node)
        node_type = data.get("nodeType", "agent")
        label = data.get("label", node_type)

        if is_annotation_node(node_type):
            metadata[node_id] = {
                "type": node_type,
                "label": label,
                "adk_name": f"note_{node_id}",
                "node_id": node_id,
                "is_annotation": True,
            }
            continue

        built = _build_adk_node(node, on_guardrail_result, context_ref)
        if context_ref is not None and callable(built) and not isinstance(built, (Agent, JoinNode, BaseNode)):
            built = wrap_with_context(
                node_id,
                built,
                context_ref,
                label=label,
                node_type=node_type,
                retries=max(0, _safe_int(data.get("retries"), 0)),
                retry_delay_sec=_safe_float(data.get("retryDelaySec"), 1.0),
                timeout_sec=(_safe_float(data.get("timeoutSec"), 0.0) or None) if data.get("timeoutSec") else None,
            )
        adk_node = _ensure_base_node(built)
        adk_name = getattr(adk_node, "name", None) or getattr(adk_node, "__name__", node_id)
        _populate_node_metadata(metadata, node, adk_name)

    author_lookup = _build_author_lookup(metadata)
    if len(_compile_cache) >= _MAX_COMPILE_CACHE:
        _compile_cache.pop(next(iter(_compile_cache)))
    _compile_cache[cache_key] = (summary, executable, metadata, author_lookup)

    workflow = _build_bound_workflow(
        graph_json,
        summary,
        executable,
        metadata,
        on_guardrail_result=on_guardrail_result,
        context_ref=context_ref,
    )
    return workflow, metadata, author_lookup