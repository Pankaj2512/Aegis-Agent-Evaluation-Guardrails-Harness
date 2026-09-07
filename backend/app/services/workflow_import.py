"""Parse and validate aegis-workflow-v1 export payloads for import."""

from __future__ import annotations

from app.services.graph_validation import GraphValidationError, validate_workflow_graph

SUPPORTED_FORMAT = "aegis-workflow-v1"


class WorkflowImportError(ValueError):
    pass


def normalize_workflow_import(raw: dict) -> tuple[str, str | None, dict]:
    """Extract name, description, and graph from an export or partial import payload."""
    if not isinstance(raw, dict):
        raise WorkflowImportError("Import payload must be a JSON object")

    fmt = raw.get("format")
    if fmt is not None and fmt != SUPPORTED_FORMAT:
        raise WorkflowImportError(f"Unsupported format: {fmt!r} (expected {SUPPORTED_FORMAT!r})")

    graph = raw.get("graph_json")
    if not graph or not isinstance(graph, dict):
        raise WorkflowImportError("Missing or invalid graph_json")

    name = (raw.get("name") or "Imported Workflow").strip() or "Imported Workflow"
    description = raw.get("description")
    if description is not None:
        description = str(description).strip() or None

    try:
        validate_workflow_graph(graph)
    except GraphValidationError as exc:
        raise WorkflowImportError(str(exc)) from exc

    return name, description, graph