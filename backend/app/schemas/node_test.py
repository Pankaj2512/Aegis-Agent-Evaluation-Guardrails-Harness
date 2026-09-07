"""Schemas for ephemeral single-node testing and expression preview.

Both endpoints are stateless/authoring aids: they never create a WorkflowRun,
NodeResult, observability event, or SSE stream. Contracts are frozen against a
parallel frontend build — keep field names and shapes stable.
"""

from __future__ import annotations

from pydantic import BaseModel


class NodeTestRequest(BaseModel):
    node_id: str
    input_text: str
    # May carry {"steps": {"<node_id>": "<output string>"}} to simulate upstream
    # node outputs so an expression like {{steps.x.output}} resolves.
    extra_context: dict | None = None
    # The node's *current* on-canvas data (unsaved inspector edits). When present
    # it is preferred over the persisted graph node so "Run test" tests exactly
    # what the user sees — and can test a not-yet-saved node the graph lacks.
    node_data: dict | None = None


class NodeTestResponse(BaseModel):
    node_id: str
    status: str  # "completed" | "failed" | "unsupported"
    output: str | None = None
    error: str | None = None
    latency_ms: int = 0


class ExpressionPreviewRequest(BaseModel):
    expression: str
    run_id: str | None = None
    sample_input: str | None = None


class ContextAvailable(BaseModel):
    input: bool
    last_output: bool
    steps: list[str]  # node ids that had outputs available


class ExpressionPreviewResponse(BaseModel):
    rendered: str | None = None
    error: str | None = None
    run_id: str | None = None  # the run actually used, if any
    context_available: ContextAvailable
