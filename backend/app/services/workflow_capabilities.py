"""Shared workflow graph capability checks."""

from __future__ import annotations


def workflow_needs_gemini(graph_json: dict | None) -> bool:
    for node in (graph_json or {}).get("nodes", []):
        data = node.get("data", {}) or {}
        node_type = data.get("nodeType")
        if node_type in {
            "agent",
            "evaluation",
            "router",
            "classifier",
            "summarizer",
            "translator",
            "extractor",
        }:
            return True
        if (
            node_type == "tool"
            and data.get("toolType") == "search"
            and data.get("searchProvider", "google") == "google"
        ):
            return True
    return False