"""Template expression rendering for workflow context (n8n-style mapping)."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

_EXPRESSION_PATTERN = re.compile(r"\{\{\s*([^}]+?)\s*\}\}")

# Legacy alias kept for backward compatibility with existing graphs.
_LEGACY_INPUT = "{{input}}"


def _resolve_path(context: dict[str, Any], path: str, node_input: str) -> Any:
    path = path.strip()
    if path in {"input", "input.text"}:
        inp = context.get("input")
        if path == "input.text":
            if isinstance(inp, dict) and "text" in inp:
                return inp["text"]
            return node_input
        return inp if inp is not None else node_input
    if path == "last_output":
        return context.get("last_output", node_input)

    parts = path.split(".")
    if not parts:
        return None

    root_key = parts[0]
    if root_key == "input":
        current: Any = context.get("input", node_input)
        parts = parts[1:]
    elif root_key == "steps" and len(parts) >= 2:
        step_id = parts[1]
        step = (context.get("steps") or {}).get(step_id, {})
        current = step
        parts = parts[2:]
    elif root_key == "memory" and len(parts) >= 2:
        memory = context.get("memory") or {}
        current = memory.get(parts[1], {})
        parts = parts[2:]
    elif root_key in {"item", "index"} and root_key in context:
        # Per-item loop variables injected by the iteration node. Only resolve
        # when present so normal nodes see no behavior change.
        current = context[root_key]
        parts = parts[1:]
    else:
        return None

    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _stringify_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def render_template(
    template: str,
    context: dict[str, Any],
    node_input: str,
) -> str:
    """Replace ``{{path}}`` placeholders using workflow context."""
    if not template:
        # Empty template means empty output — not a silent passthrough of input.
        return ""

    if template == _LEGACY_INPUT:
        return node_input

    if "{{" not in template:
        return template

    def _replace(match: re.Match[str]) -> str:
        path = match.group(1).strip()
        if path == "input":
            return _stringify_value(node_input)
        value = _resolve_path(context, path, node_input)
        if value is None and path.startswith("steps."):
            # Consistent with every other missing path: render empty rather
            # than leaking the literal placeholder into output.
            logger.debug("Expression path %r resolved to no value", path)
        return _stringify_value(value)

    return _EXPRESSION_PATTERN.sub(_replace, template)


def template_uses_expressions(template: str | None) -> bool:
    if not template:
        return False
    return "{{" in template


def _render_operand(value: str, context: dict[str, Any], node_input: str) -> str:
    if "{{" in value:
        return render_template(value, context, node_input)
    return value


def evaluate_condition(
    left: str,
    operator: str,
    right: str | None,
    context: dict[str, Any],
    node_input: str,
) -> bool:
    """Evaluate a structured IF condition (n8n-style, expression operands)."""
    left_val = _render_operand(left, context, node_input).strip()
    right_val = _render_operand(right or "", context, node_input).strip()
    op = (operator or "eq").lower()

    if op == "empty":
        return not left_val
    if op == "not_empty":
        return bool(left_val)
    if op == "contains":
        return right_val in left_val
    if op == "not_contains":
        return right_val not in left_val
    if op == "eq":
        return left_val == right_val
    if op == "neq":
        return left_val != right_val
    if op in {"gt", "lt"}:
        left_num = _coerce_number(left_val)
        right_num = _coerce_number(right_val)
        if left_num is not None and right_num is not None:
            return left_num > right_num if op == "gt" else left_num < right_num
        # Only one (or neither) side is numeric — fall back to string ordering.
        return left_val > right_val if op == "gt" else left_val < right_val
    return left_val == right_val


def _coerce_number(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None