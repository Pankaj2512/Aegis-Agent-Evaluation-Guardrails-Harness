"""Build a deploy descriptor (invoke URL, cURL, MCP tool) for a published workflow.

Serialization only — derives an MCP tool descriptor's input schema from the
workflow's ``input_schema`` node in ``graph_json`` (falls back to a single
free-text ``input`` field when no such node exists). No new execution path.
"""

from __future__ import annotations

import json
from typing import Any

# Map Aegis input-field types → JSON Schema types (MCP tools use JSON Schema).
_FIELD_TYPE_TO_JSON_SCHEMA: dict[str, str] = {
    "string": "string",
    "text": "string",
    "number": "number",
    "integer": "integer",
    "int": "integer",
    "float": "number",
    "boolean": "boolean",
    "bool": "boolean",
    "array": "array",
    "list": "array",
    "object": "object",
    "json": "object",
}


def _node_type(node: dict) -> str:
    return (node.get("data") or {}).get("nodeType", "")


def find_input_schema_fields(graph_json: dict | None) -> list[dict[str, Any]]:
    """Return the first input_schema node's ``inputFields`` (or [])."""
    for node in (graph_json or {}).get("nodes", []):
        if _node_type(node) == "input_schema":
            fields = (node.get("data") or {}).get("inputFields") or []
            return [f for f in fields if isinstance(f, dict) and f.get("key")]
    return []


def build_mcp_input_schema(graph_json: dict | None) -> dict[str, Any]:
    """Derive a JSON Schema object for the MCP tool's input.

    Uses the workflow's input_schema node fields when present; otherwise a single
    required free-text ``input`` field (matching the /invoke payload contract).
    """
    fields = find_input_schema_fields(graph_json)
    if not fields:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Free-text input for the workflow"}
            },
            "required": ["input"],
        }

    properties: dict[str, Any] = {}
    required: list[str] = []
    for field in fields:
        key = str(field["key"])
        raw_type = str(field.get("type") or "string").lower()
        json_type = _FIELD_TYPE_TO_JSON_SCHEMA.get(raw_type, "string")
        prop: dict[str, Any] = {"type": json_type}
        if field.get("description"):
            prop["description"] = str(field["description"])
        if field.get("default") is not None:
            prop["default"] = field["default"]
        properties[key] = prop
        if field.get("required"):
            required.append(key)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _sanitize_tool_name(name: str) -> str:
    slug = "".join(c if c.isalnum() else "_" for c in (name or "workflow").lower()).strip("_")
    return slug or "workflow"


def build_deploy_descriptor(
    *,
    workflow_id: str,
    workflow_name: str,
    description: str | None,
    published_version_id: str,
    published_version_number: int | None,
    graph_json: dict | None,
    base_url: str,
) -> dict[str, Any]:
    invoke_path = f"/v1/workflows/{workflow_id}/invoke"
    invoke_url = f"{base_url.rstrip('/')}{invoke_path}" if base_url else invoke_path

    input_schema = build_mcp_input_schema(graph_json)
    example_input = "Hello"

    curl_snippet = (
        f"curl -X POST '{invoke_url}' \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -H 'X-Aegis-API-Key: <YOUR_API_KEY>' \\\n"
        f"  -d '{json.dumps({'input': example_input})}'"
    )

    tool_name = f"invoke_{_sanitize_tool_name(workflow_name)}"
    mcp_tool = {
        "name": tool_name,
        "description": (description or f"Invoke the '{workflow_name}' Aegis workflow.").strip(),
        "input_schema": input_schema,
    }

    return {
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
        "published_version_id": published_version_id,
        "published_version_number": published_version_number,
        "invoke_url": invoke_url,
        "invoke_path": invoke_path,
        "method": "POST",
        "curl": curl_snippet,
        "mcp_tool": mcp_tool,
    }
