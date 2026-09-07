"""Canonical node type metadata for the agentic workflow builder."""

from __future__ import annotations

from typing import TypedDict


class NodeTypeMeta(TypedDict, total=False):
    type: str
    label: str
    category: str
    description: str
    executable: bool
    supports_expressions: bool
    branches: bool


NODE_REGISTRY: list[NodeTypeMeta] = [
    {"type": "trigger", "label": "Trigger", "category": "flow", "executable": True},
    {"type": "end", "label": "End", "category": "flow", "executable": True},
    {"type": "input_schema", "label": "Input Schema", "category": "flow", "description": "Define workflow input fields (Lyzr-style)", "executable": True},
    {"type": "if", "label": "IF", "category": "flow", "description": "Expression branch true/false (n8n-style)", "executable": True, "branches": True},
    {"type": "switch", "label": "Switch", "category": "flow", "description": "Route by value match", "executable": True, "branches": True},
    {"type": "filter", "label": "Filter", "category": "flow", "description": "Pass data only when condition matches", "executable": True},
    {"type": "agent", "label": "LLM Agent", "category": "llm", "executable": True, "supports_expressions": True},
    {"type": "summarizer", "label": "Summarizer", "category": "llm", "executable": True},
    {"type": "translator", "label": "Translator", "category": "llm", "executable": True},
    {"type": "extractor", "label": "Extractor", "category": "llm", "executable": True},
    {"type": "tool", "label": "Tool", "category": "tools", "executable": True, "supports_expressions": True},
    {"type": "transform", "label": "Transform", "category": "data", "executable": True, "supports_expressions": True},
    {"type": "set_fields", "label": "Set Fields", "category": "data", "description": "Map fields into workflow context", "executable": True, "supports_expressions": True},
    {"type": "code", "label": "Code", "category": "data", "description": "Sandboxed Python transform (n8n-style)", "executable": True},
    {"type": "memory_store", "label": "Memory Store", "category": "data", "description": "Persist a value in run memory (Lyzr Cognis)", "executable": True, "supports_expressions": True},
    {"type": "memory_retrieve", "label": "Memory Retrieve", "category": "data", "description": "Read a value from run memory", "executable": True, "supports_expressions": True},
    {"type": "kb_retrieve", "label": "KB Retrieve", "category": "data", "description": "Retrieve knowledge-base chunks (RAG-lite)", "executable": True, "supports_expressions": True},
    {"type": "human_approval", "label": "Human Approval", "category": "flow", "description": "Pause for human review (Lyzr SuperFlow)", "executable": True, "supports_expressions": True},
    {"type": "sub_workflow", "label": "Sub-workflow", "category": "flow", "description": "Execute another workflow (n8n Execute Workflow)", "executable": True, "supports_expressions": True},
    {"type": "integration", "label": "Integration", "category": "tools", "description": "Slack, Discord, Email, or Postgres", "executable": True, "supports_expressions": True},
    {"type": "json_parse", "label": "JSON Parse", "category": "data", "executable": True},
    {"type": "delay", "label": "Delay", "category": "data", "executable": True},
    {"type": "evaluation", "label": "Evaluation", "category": "quality", "executable": True},
    {"type": "guardrail", "label": "Guardrail", "category": "quality", "executable": True},
    {"type": "router", "label": "Router", "category": "flow", "executable": True, "branches": True},
    {"type": "classifier", "label": "Classifier", "category": "flow", "executable": True, "branches": True},
    {"type": "join", "label": "Join", "category": "flow", "executable": True},
    {"type": "iteration", "label": "Iteration", "category": "flow", "description": "Map logic over each item of a list (Dify-style)", "executable": True, "supports_expressions": True},
    {"type": "note", "label": "Sticky Note", "category": "annotate", "executable": False},
    {"type": "group", "label": "Group", "category": "annotate", "description": "Visual grouping frame (display-only)", "executable": False},
]

NODE_TYPES_BY_ID: dict[str, NodeTypeMeta] = {n["type"]: n for n in NODE_REGISTRY}


def get_node_meta(node_type: str) -> NodeTypeMeta | None:
    return NODE_TYPES_BY_ID.get(node_type)