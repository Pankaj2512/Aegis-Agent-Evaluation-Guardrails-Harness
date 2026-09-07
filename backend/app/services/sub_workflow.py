"""Execute a child workflow from a Sub-workflow node (n8n Execute Workflow)."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any
from uuid import UUID

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from sqlalchemy.orm import joinedload

from app.db import models
from app.db.database import SessionLocal
from app.services.eval import EvalThresholdBlockedError
from app.services.guardrail import GuardrailBlockedError
from app.services.workflow_context import WorkflowContext

MAX_SUB_WORKFLOW_DEPTH = 8


async def execute_sub_workflow(
    workflow_id: UUID,
    input_text: str,
    *,
    user_id: UUID | None = None,
    parent_context: dict[str, Any] | None = None,
) -> str:
    call_stack = list((parent_context or {}).get("_sub_workflow_stack") or [])
    workflow_key = str(workflow_id)
    if workflow_key in call_stack:
        return f"Sub-workflow error: circular dependency detected ({workflow_key})"
    if len(call_stack) >= MAX_SUB_WORKFLOW_DEPTH:
        return (
            f"Sub-workflow error: max nesting depth ({MAX_SUB_WORKFLOW_DEPTH}) exceeded"
        )

    # Run the whole DB unit of work in a worker thread so the sync SQLAlchemy
    # session never blocks the event loop. The session is opened, read, and
    # closed entirely inside the thread; only the plain graph_json dict escapes.
    def _load_graph_json() -> dict | None:
        db = SessionLocal()
        try:
            query = (
                db.query(models.Workflow)
                .options(joinedload(models.Workflow.versions))
                .filter(models.Workflow.id == workflow_id)
            )
            if user_id:
                query = query.filter(models.Workflow.user_id == user_id)
            workflow = query.first()
            if not workflow or not workflow.versions:
                return None
            version = max(workflow.versions, key=lambda v: v.version_number)
            return version.graph_json
        finally:
            db.close()

    graph_json = await asyncio.to_thread(_load_graph_json)
    if graph_json is None:
        return f"Sub-workflow error: workflow {workflow_id} not found"

    child_context = WorkflowContext.from_input(input_text)
    context_ref = child_context.to_dict()
    context_ref["_sub_workflow_stack"] = [*call_stack, workflow_key]
    if parent_context:
        context_ref["parent"] = {
            "input": parent_context.get("input"),
            "last_output": parent_context.get("last_output"),
        }

    from app.services.compiler import compile_workflow

    compiled, metadata, _author_lookup = compile_workflow(
        graph_json, context_ref=context_ref
    )
    session_service = InMemorySessionService()
    runner = Runner(
        app_name="aegis-sub",
        node=compiled,
        session_service=session_service,
        auto_create_session=True,
    )

    final_output: str | None = None
    try:
        async for event in runner.run_async(
            user_id="aegis-sub-user",
            session_id=str(uuid.uuid4()),
            new_message=types.Content(parts=[types.Part(text=input_text)]),
        ):
            text = getattr(event, "output", None) or getattr(event, "content", None)
            if text:
                if hasattr(text, "parts"):
                    parts = [getattr(p, "text", "") for p in text.parts if getattr(p, "text", None)]
                    if parts:
                        final_output = "\n".join(parts)
                elif isinstance(text, str):
                    final_output = text
    except GuardrailBlockedError as exc:
        # Contain child failures here so the child's node_id never propagates
        # into the parent executor's metadata lookup (which would KeyError).
        return f"Sub-workflow error: guardrail blocked at child node {exc.node_id}: {exc}"
    except EvalThresholdBlockedError as exc:
        return (
            f"Sub-workflow error: eval threshold not met at child node "
            f"{exc.node_id}: {exc}"
        )

    end_ids = [nid for nid, meta in metadata.items() if meta.get("type") == "end"]
    if not final_output and end_ids:
        return child_context.to_dict().get("last_output") or input_text
    return final_output or child_context.to_dict().get("last_output") or input_text