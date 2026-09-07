from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Callable

from uuid import UUID

from app.db import models
from app.db.database import SessionLocal
from app.http_client import get_http_client
from app.services.approval_service import HumanApprovalDenied, wait_for_approval
from app.services.code_sandbox import run_sandboxed_code
from app.services.credentials import get_user_credential, resolve_credential
from app.services.expressions import evaluate_condition, render_template
from app.services.integrations import (
    run_discord_integration,
    run_email_integration,
    run_postgres_integration,
    run_slack_integration,
)
from app.services.knowledge_base import retrieve_documents
from app.services.persistent_memory import upsert_memory_entry
from app.services.routing_models import RouterDecision
from app.services.url_safety import safe_http_request, validate_http_url

MAX_DELAY_SECONDS = 30
MAX_HTTP_RESPONSE_CHARS = 50_000


def _make_transform_fn(
    node_id: str,
    template: str,
    adk_name: str,
    context_ref: dict | None = None,
) -> Callable[[str], str]:
    tpl = template or "{{input}}"

    def transform(node_input: str) -> str:
        ctx = context_ref or {"input": {"text": node_input}, "steps": {}, "last_output": node_input}
        return render_template(tpl, ctx, str(node_input))

    transform.__name__ = adk_name
    return transform


def _make_json_parse_fn(node_id: str, json_path: str | None, adk_name: str) -> Callable[[str], str]:
    def json_parse(node_input: str) -> str:
        text = str(node_input).strip()
        parsed: Any = None

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}|\[[\s\S]*\]", text)
            if match:
                try:
                    parsed = json.loads(match.group())
                except json.JSONDecodeError:
                    return "JSON parse error: no valid JSON found in input"
            else:
                return "JSON parse error: no valid JSON found in input"

        if json_path:
            current = parsed
            for key in json_path.split("."):
                if isinstance(current, dict) and key in current:
                    current = current[key]
                elif isinstance(current, list):
                    try:
                        idx = int(key)
                        if 0 <= idx < len(current):
                            current = current[idx]
                        else:
                            return f"JSON path '{json_path}' index out of range"
                    except ValueError:
                        return f"JSON path '{json_path}' not found"
                else:
                    return f"JSON path '{json_path}' not found"
            return json.dumps(current) if not isinstance(current, str) else current

        return json.dumps(parsed, indent=2) if isinstance(parsed, (dict, list)) else str(parsed)

    json_parse.__name__ = adk_name
    return json_parse


def _make_delay_fn(node_id: str, seconds: float, adk_name: str) -> Callable[[str], Any]:
    raw = 1.0 if seconds is None or seconds == "" else float(seconds)
    delay_secs = max(0.0, min(raw, MAX_DELAY_SECONDS))

    async def delay(node_input: str) -> str:
        await asyncio.sleep(delay_secs)
        return str(node_input)

    delay.__name__ = adk_name
    return delay


def _make_http_fn(
    node_id: str,
    method: str,
    url: str,
    headers: dict[str, str],
    body_template: str | None,
    adk_name: str,
    context_ref: dict | None = None,
) -> Callable[[str], Any]:
    http_method = (method or "GET").upper()
    raw_url = url or ""

    async def http_request(node_input: str) -> str:
        ctx = context_ref or {"input": {"text": node_input}, "steps": {}, "last_output": node_input}
        target_url = render_template(raw_url, ctx, str(node_input)).strip()
        if not target_url:
            return "HTTP error: HTTP node: URL is required"
        body = None
        if body_template:
            body = render_template(body_template, ctx, str(node_input))
        elif http_method in {"POST", "PUT", "PATCH"}:
            body = str(node_input)

        rendered_headers = {}
        for k, v in (headers or {}).items():
            rendered_headers[k] = render_template(v, ctx, str(node_input))

        try:
            await asyncio.to_thread(validate_http_url, target_url)
            client = get_http_client()
            response = await safe_http_request(
                client,
                http_method,
                target_url,
                headers=rendered_headers or None,
                content=body.encode() if body else None,
                max_body_bytes=MAX_HTTP_RESPONSE_CHARS,
            )
            text = response.text[:MAX_HTTP_RESPONSE_CHARS]
            return f"HTTP {response.status_code}\n{text}"
        except ValueError as exc:
            return f"HTTP error: {exc}"
        except Exception as exc:
            return f"HTTP error: {exc}"

    http_request.__name__ = adk_name
    return http_request


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = str(text).strip()
    if not stripped:
        return {}
    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return {"text": stripped}


def _merge_context_input(context_ref: dict[str, Any], updates: dict[str, Any]) -> None:
    base = context_ref.get("input")
    if isinstance(base, dict):
        context_ref["input"] = {**base, **updates}
    else:
        context_ref["input"] = updates


def _make_input_schema_fn(
    node_id: str,
    fields: list[dict[str, Any]],
    adk_name: str,
    context_ref: dict[str, Any] | None = None,
) -> Callable[[str], str]:
    def input_schema(node_input: str) -> str:
        ctx = context_ref or {"input": {}, "steps": {}, "last_output": node_input}
        raw = _parse_json_object(node_input)
        structured: dict[str, Any] = {}
        missing_required: list[str] = []
        for field in fields or []:
            key = field.get("key")
            if not key:
                continue
            if key in raw and raw[key] not in (None, ""):
                structured[key] = raw[key]
            elif field.get("default") is not None:
                structured[key] = field["default"]
            elif field.get("required"):
                missing_required.append(key)
            else:
                structured[key] = raw.get(key, "")
        if missing_required:
            raise ValueError(
                "Input schema: missing required field(s): "
                + ", ".join(missing_required)
            )
        if "text" not in structured:
            structured["text"] = raw.get("text", node_input)
        if context_ref is not None:
            _merge_context_input(context_ref, structured)
        return json.dumps(structured, ensure_ascii=False)

    input_schema.__name__ = adk_name
    return input_schema


def _make_set_fields_fn(
    node_id: str,
    field_map: dict[str, str],
    adk_name: str,
    context_ref: dict[str, Any] | None = None,
) -> Callable[[str], str]:
    def set_fields(node_input: str) -> str:
        ctx = context_ref or {"input": {"text": node_input}, "steps": {}, "last_output": node_input}
        base = ctx.get("input")
        if not isinstance(base, dict):
            base = _parse_json_object(node_input)
        result = dict(base)
        for key, template in (field_map or {}).items():
            result[key] = render_template(template, ctx, str(node_input))
        if context_ref is not None:
            _merge_context_input(context_ref, result)
        return json.dumps(result, ensure_ascii=False)

    set_fields.__name__ = adk_name
    return set_fields


def _make_filter_fn(
    node_id: str,
    left: str,
    operator: str,
    right: str | None,
    adk_name: str,
    context_ref: dict[str, Any] | None = None,
) -> Callable[[str], str]:
    def filter_node(node_input: str) -> str:
        ctx = context_ref or {"input": {"text": node_input}, "steps": {}, "last_output": node_input}
        if evaluate_condition(left, operator, right, ctx, str(node_input)):
            return str(node_input)
        return ""

    filter_node.__name__ = adk_name
    return filter_node


def _make_if_fn(
    node_id: str,
    left: str,
    operator: str,
    right: str | None,
    adk_name: str,
    context_ref: dict[str, Any] | None = None,
) -> Callable[[str], RouterDecision]:
    def if_node(node_input: str) -> RouterDecision:
        ctx = context_ref or {"input": {"text": node_input}, "steps": {}, "last_output": node_input}
        passed = evaluate_condition(left, operator, right, ctx, str(node_input))
        route = "true" if passed else "false"
        return RouterDecision(route=route, reasoning=f"Condition {'passed' if passed else 'failed'}")

    if_node.__name__ = adk_name
    return if_node


def _make_switch_fn(
    node_id: str,
    value_expr: str,
    cases: list[str],
    default_route: str,
    adk_name: str,
    context_ref: dict[str, Any] | None = None,
) -> Callable[[str], RouterDecision]:
    def switch_node(node_input: str) -> RouterDecision:
        ctx = context_ref or {"input": {"text": node_input}, "steps": {}, "last_output": node_input}
        value = render_template(value_expr or "{{last_output}}", ctx, str(node_input)).strip()
        route = default_route or "default"
        for case in cases or []:
            if value == case.strip():
                route = case.strip()
                break
        return RouterDecision(route=route, reasoning=f"Switch matched '{route}' for value '{value}'")

    switch_node.__name__ = adk_name
    return switch_node


def _ensure_memory_bucket(context_ref: dict[str, Any], namespace: str) -> dict[str, Any]:
    memory = context_ref.setdefault("memory", {})
    if not isinstance(memory, dict):
        memory = {}
        context_ref["memory"] = memory
    bucket = memory.setdefault(namespace, {})
    if not isinstance(bucket, dict):
        bucket = {}
        memory[namespace] = bucket
    return bucket


def _make_code_fn(
    node_id: str,
    code: str,
    adk_name: str,
    context_ref: dict[str, Any] | None = None,
) -> Callable[[str], str]:
    source = code or "result = last_output"

    def code_node(node_input: str) -> str:
        ctx = context_ref or {"input": {"text": node_input}, "steps": {}, "last_output": node_input, "memory": {}}
        try:
            return run_sandboxed_code(source, ctx, str(node_input))
        except Exception as exc:
            return f"Code error: {exc}"

    code_node.__name__ = adk_name
    return code_node


def _load_workflow_kb_documents(workflow_id: str) -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = (
            db.query(models.KnowledgeDocument)
            .filter(models.KnowledgeDocument.workflow_id == UUID(workflow_id))
            .order_by(models.KnowledgeDocument.updated_at.desc())
            .all()
        )
        return [
            {
                "id": str(row.id),
                "title": row.title,
                "text": row.text,
                "embedding": row.embedding,
            }
            for row in rows
        ]
    finally:
        db.close()


def _make_memory_store_fn(
    node_id: str,
    namespace: str,
    key_expr: str,
    value_expr: str,
    adk_name: str,
    context_ref: dict[str, Any] | None = None,
    *,
    persistent: bool = False,
) -> Callable[[str], str]:
    ns_default = namespace or "default"

    def memory_store(node_input: str) -> str:
        ctx = context_ref or {"input": {"text": node_input}, "steps": {}, "last_output": node_input, "memory": {}}
        ns = render_template(ns_default, ctx, str(node_input)).strip() or "default"
        key = render_template(key_expr or "{{input.text}}", ctx, str(node_input)).strip()
        value = render_template(value_expr or "{{last_output}}", ctx, str(node_input))
        target = context_ref if context_ref is not None else ctx
        bucket = _ensure_memory_bucket(target, ns)
        bucket[key] = value

        if persistent and context_ref and context_ref.get("_workflow_id") and key:
            from app.services.persistent_memory import queue_memory_write

            queue_memory_write(context_ref, UUID(str(context_ref["_workflow_id"])), ns, key, value)

        return json.dumps(
            {"stored": True, "namespace": ns, "key": key, "persistent": persistent},
            ensure_ascii=False,
        )

    memory_store.__name__ = adk_name
    return memory_store


def _make_memory_retrieve_fn(
    node_id: str,
    namespace: str,
    key_expr: str,
    adk_name: str,
    context_ref: dict[str, Any] | None = None,
) -> Callable[[str], str]:
    ns_default = namespace or "default"

    def memory_retrieve(node_input: str) -> str:
        ctx = context_ref or {"input": {"text": node_input}, "steps": {}, "last_output": node_input, "memory": {}}
        ns = render_template(ns_default, ctx, str(node_input)).strip() or "default"
        key = render_template(key_expr or "{{input.text}}", ctx, str(node_input)).strip()
        memory_root = context_ref if context_ref is not None else ctx
        memory = memory_root.get("memory", {})
        if not isinstance(memory, dict):
            return ""
        bucket = memory.get(ns, {})
        if not isinstance(bucket, dict):
            return ""
        return str(bucket.get(key, ""))

    memory_retrieve.__name__ = adk_name
    return memory_retrieve


def _make_kb_retrieve_fn(
    node_id: str,
    query_expr: str,
    documents: list[dict[str, Any]],
    top_k: int,
    adk_name: str,
    context_ref: dict[str, Any] | None = None,
    *,
    kb_source: str = "inline",
    retrieval_method: str = "bm25",
) -> Callable[[str], str]:
    def kb_retrieve(node_input: str) -> str:
        ctx = context_ref or {"input": {"text": node_input}, "steps": {}, "last_output": node_input, "memory": {}}
        query = render_template(query_expr or "{{last_output}}", ctx, str(node_input))
        docs = list(documents or [])
        if kb_source == "workflow" and context_ref and context_ref.get("_workflow_id"):
            cached = context_ref.get("_kb_documents")
            docs = list(cached) if cached is not None else _load_workflow_kb_documents(
                str(context_ref["_workflow_id"])
            )
        if retrieval_method == "embedding" and context_ref and context_ref.get("_workflow_id"):
            from uuid import UUID

            from app.services.vector_search import retrieve_documents as vector_retrieve

            hits = vector_retrieve(
                UUID(str(context_ref["_workflow_id"])),
                query,
                docs,
                top_k=top_k,
            )
        else:
            hits = retrieve_documents(query, docs, top_k=top_k, method=retrieval_method)
        return json.dumps({"query": query, "results": hits, "source": kb_source}, ensure_ascii=False)

    kb_retrieve.__name__ = adk_name
    return kb_retrieve


def _make_human_approval_fn(
    node_id: str,
    review_template: str,
    adk_name: str,
    context_ref: dict[str, Any] | None = None,
) -> Callable[[str], Any]:
    review_tpl = review_template or "{{last_output}}"

    async def human_approval(node_input: str) -> str:
        ctx = context_ref or {"input": {"text": node_input}, "steps": {}, "last_output": node_input, "memory": {}}
        review = render_template(review_tpl, ctx, str(node_input))
        run_id = str(context_ref.get("_run_id") if context_ref else "")
        emit = context_ref.get("_emit") if context_ref else None

        if run_id and context_ref is not None:
            mark_fn = context_ref.get("_mark_awaiting_approval")
            if callable(mark_fn):
                await mark_fn(run_id, node_id, review)
            if callable(emit):
                await emit(
                    {
                        "type": "approval_required",
                        "run_id": run_id,
                        "node_id": node_id,
                        "review": review,
                    }
                )

        decision = (
            await wait_for_approval(run_id, node_id=node_id)
            if run_id
            else {"approved": True, "comment": ""}
        )
        if not decision.get("approved"):
            raise HumanApprovalDenied(node_id, str(decision.get("comment") or ""))
        return str(node_input)

    human_approval.__name__ = adk_name
    return human_approval


def _load_credential(
    user_id: str | None,
    credential_id: str | None,
    credential_name: str | None,
) -> dict[str, Any]:
    if not user_id:
        return {}
    db = SessionLocal()
    try:
        uid = UUID(user_id)
        cred = get_user_credential(
            db,
            uid,
            credential_id=UUID(credential_id) if credential_id else None,
            name=credential_name,
        )
        return resolve_credential(cred)
    finally:
        db.close()


def _make_integration_fn(
    node_id: str,
    integration_type: str,
    credential_id: str | None,
    credential_name: str | None,
    message_template: str | None,
    subject_template: str | None,
    body_template: str | None,
    query_template: str | None,
    adk_name: str,
    context_ref: dict[str, Any] | None = None,
) -> Callable[[str], Any]:
    kind = (integration_type or "slack").lower()

    async def integration(node_input: str) -> str:
        ctx = context_ref or {"input": {"text": node_input}, "steps": {}, "last_output": node_input, "memory": {}}
        config = await asyncio.to_thread(
            _load_credential,
            str(context_ref.get("_user_id")) if context_ref else None,
            credential_id,
            credential_name,
        )
        if not config:
            return f"Integration error: credential not found for {kind}"

        if kind == "slack":
            webhook = config.get("webhook_url")
            if not webhook:
                return "Integration error: slack credential missing webhook_url"
            return await run_slack_integration(webhook, message_template or "{{last_output}}", ctx, node_input)

        if kind == "discord":
            webhook = config.get("webhook_url")
            if not webhook:
                return "Integration error: discord credential missing webhook_url"
            return await run_discord_integration(webhook, message_template or "{{last_output}}", ctx, node_input)

        if kind == "email":
            return await run_email_integration(
                config,
                subject_template or "Aegis notification",
                body_template or "{{last_output}}",
                ctx,
                node_input,
            )

        if kind == "postgres":
            return await run_postgres_integration(
                config,
                query_template or "SELECT 1",
                ctx,
                node_input,
            )

        return f"Integration error: unsupported type '{kind}'"

    integration.__name__ = adk_name
    return integration


def _make_sub_workflow_fn(
    node_id: str,
    workflow_id: str | None,
    input_template: str | None,
    adk_name: str,
    context_ref: dict[str, Any] | None = None,
) -> Callable[[str], Any]:
    child_id = workflow_id or ""
    input_tpl = input_template or "{{last_output}}"

    async def sub_workflow(node_input: str) -> str:
        if not child_id:
            return "Sub-workflow error: no workflow_id configured"
        ctx = context_ref or {"input": {"text": node_input}, "steps": {}, "last_output": node_input, "memory": {}}
        child_input = render_template(input_tpl, ctx, str(node_input))
        user_id = context_ref.get("_user_id") if context_ref else None
        from app.services.sub_workflow import execute_sub_workflow

        return await execute_sub_workflow(
            UUID(child_id),
            child_input,
            user_id=UUID(user_id) if user_id else None,
            parent_context=ctx,
        )

    sub_workflow.__name__ = adk_name
    return sub_workflow


MAX_ITERATION_ITEMS = 100
MAX_ITERATION_CONCURRENCY = 5


def _parse_iteration_items(text: str) -> list[Any]:
    """Resolve the items expression to a list: JSON array, else newline lines."""
    stripped = str(text).strip()
    if not stripped:
        return []
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, list):
        return parsed
    return [line for line in stripped.splitlines() if line.strip()]


def _stringify_item(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, (dict, list)):
        return json.dumps(item, ensure_ascii=False)
    return str(item)


def _coerce_item_output(text: str) -> Any:
    """Parse a per-item output into JSON when it is an object/array; else keep
    the raw string so scalar outputs are not surprisingly retyped."""
    stripped = str(text).strip()
    if not stripped:
        return text
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return text
    if isinstance(parsed, (dict, list)):
        return parsed
    return text


def _make_iteration_fn(
    node_id: str,
    items_expression: str,
    item_template: str,
    sub_workflow_id: str | None,
    mode: str,
    max_items: int,
    on_item_error: str,
    adk_name: str,
    context_ref: dict[str, Any] | None = None,
) -> Callable[[str], Any]:
    """Map logic over each item of a list inside a single node (Dify-style).

    The graph stays a DAG — the loop lives entirely inside this handler. Each
    item is either rendered through ``item_template`` (with ``{{item}}`` /
    ``{{index}}`` plus the normal expression context) or fed as input to a
    sub-workflow. Output is a JSON array of per-item outputs, order preserved.
    """
    items_expr = items_expression or "{{last_output}}"
    per_item_template = item_template or "{{item}}"
    child_id = (sub_workflow_id or "").strip()
    run_mode = "parallel" if str(mode or "").lower() == "parallel" else "sequential"
    cap = max(1, min(_safe_iteration_int(max_items, 25), MAX_ITERATION_ITEMS))
    error_mode = "skip" if str(on_item_error or "").lower() == "skip" else "fail"

    async def iteration(node_input: str) -> str:
        ctx = context_ref or {
            "input": {"text": node_input},
            "steps": {},
            "last_output": node_input,
            "memory": {},
        }
        rendered = render_template(items_expr, ctx, str(node_input))
        items = _parse_iteration_items(rendered)
        total = len(items)
        truncated = total > cap
        if truncated:
            items = items[:cap]

        async def _process(index: int, item: Any) -> Any:
            # Shallow copy so {{item}}/{{index}} resolve per item without
            # mutating the shared context. node_input stays the iteration
            # node's input so {{input}}/{{last_output}} keep normal meaning.
            item_ctx = {**ctx, "item": item, "index": index}
            if child_id:
                from app.services.sub_workflow import execute_sub_workflow

                user_id = ctx.get("_user_id")
                output = await execute_sub_workflow(
                    UUID(child_id),
                    _stringify_item(item),
                    user_id=UUID(user_id) if user_id else None,
                    parent_context=item_ctx,
                )
            else:
                output = render_template(per_item_template, item_ctx, str(node_input))
            return _coerce_item_output(output)

        async def _process_guarded(index: int, item: Any) -> Any:
            try:
                return await _process(index, item)
            except Exception as exc:  # noqa: BLE001 — per-item error policy
                if error_mode == "skip":
                    return {"index": index, "error": str(exc)}
                raise

        if run_mode == "parallel" and len(items) > 1:
            semaphore = asyncio.Semaphore(MAX_ITERATION_CONCURRENCY)

            async def _bounded(index: int, item: Any) -> Any:
                async with semaphore:
                    return await _process_guarded(index, item)

            results = list(
                await asyncio.gather(
                    *(_bounded(i, item) for i, item in enumerate(items))
                )
            )
        else:
            results = []
            for i, item in enumerate(items):
                results.append(await _process_guarded(i, item))

        if truncated and context_ref is not None:
            note = {"truncated": True, "processed": cap, "total": total}
            context_ref.setdefault("_iteration_notes", {})[node_id] = note
            emit = context_ref.get("_emit")
            if callable(emit):
                await emit({"type": "iteration_truncated", "node_id": node_id, **note})

        return json.dumps(results, ensure_ascii=False, default=str)

    iteration.__name__ = adk_name
    return iteration


def _safe_iteration_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def is_annotation_node(node_type: str | None) -> bool:
    return node_type in {"note", "group"}


def filter_executable_graph(graph_json: dict) -> dict:
    """Strip annotation nodes and dangling edges for compilation/validation."""
    nodes = graph_json.get("nodes", [])
    executable_ids = {
        n["id"] for n in nodes if not is_annotation_node(_node_data(n).get("nodeType"))
    }
    filtered_nodes = [n for n in nodes if n["id"] in executable_ids]
    filtered_edges = [
        e
        for e in graph_json.get("edges", [])
        if e.get("source") in executable_ids and e.get("target") in executable_ids
    ]
    return {"nodes": filtered_nodes, "edges": filtered_edges}


def _node_data(node: dict) -> dict:
    return node.get("data", {}) or {}