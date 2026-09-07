"""AI-assist endpoints: generate workflows, suggest nodes, explain runs.

Routes are sync ``def`` per codebase convention (FastAPI runs them in a
threadpool), which suits the blocking google.genai calls.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app.auth.deps import get_current_user_id
from app.config import settings
from app.db import models
from app.db.database import get_db
from app.schemas.assist import (
    CompareRequest,
    CompareResponse,
    EditGraphRequest,
    EditGraphResponse,
    ExplainRunRequest,
    ExplainRunResponse,
    GenerateSchemaRequest,
    GenerateSchemaResponse,
    GenerateWorkflowRequest,
    GenerateWorkflowResponse,
    SuggestNodesRequest,
    SuggestNodesResponse,
)
from app.services import assist as assist_service
from app.services.assist import AssistError

router = APIRouter(prefix="/api/assist", tags=["assist"])

_NO_KEY_DETAIL = (
    "GOOGLE_API_KEY is not configured. Add it to .env to run LLM workflows."
)


def _require_api_key() -> None:
    if not settings.google_api_key:
        raise HTTPException(status_code=400, detail=_NO_KEY_DETAIL)


def _get_user_run(db: Session, run_id: UUID, user_id: UUID) -> models.WorkflowRun:
    """Local copy of the run-ownership join (runs.py is not edited)."""
    run = (
        db.query(models.WorkflowRun)
        .options(
            joinedload(models.WorkflowRun.version).joinedload(models.WorkflowVersion.workflow),
            joinedload(models.WorkflowRun.node_results),
        )
        .join(models.WorkflowVersion)
        .join(models.Workflow)
        .filter(models.WorkflowRun.id == run_id, models.Workflow.user_id == user_id)
        .first()
    )
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/generate-workflow", response_model=GenerateWorkflowResponse)
def generate_workflow(
    payload: GenerateWorkflowRequest,
    user_id: UUID = Depends(get_current_user_id),
) -> GenerateWorkflowResponse:
    _require_api_key()
    assist_service.check_assist_rate_limit(str(user_id), "generate")
    try:
        graph, notes = assist_service.generate_workflow(payload.description)
    except AssistError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — LLM/transport failure
        raise HTTPException(
            status_code=502, detail="Workflow generation failed. Please try again."
        ) from exc
    return GenerateWorkflowResponse(graph=graph, notes=notes)


@router.post("/suggest-nodes", response_model=SuggestNodesResponse)
def suggest_nodes(
    payload: SuggestNodesRequest,
    user_id: UUID = Depends(get_current_user_id),
) -> SuggestNodesResponse:
    _require_api_key()
    assist_service.check_assist_rate_limit(str(user_id), "suggest")
    try:
        suggestions = assist_service.suggest_nodes(
            payload.graph, payload.selected_node_id, str(user_id), payload.history
        )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — LLM/transport failure
        raise HTTPException(
            status_code=502, detail="Node suggestion failed. Please try again."
        ) from exc
    return SuggestNodesResponse(suggestions=suggestions)


@router.post("/explain-run", response_model=ExplainRunResponse)
def explain_run(
    payload: ExplainRunRequest,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> ExplainRunResponse:
    _require_api_key()
    assist_service.check_assist_rate_limit(str(user_id), "explain")
    run = _get_user_run(db, payload.run_id, user_id)
    if run.status != "failed":
        raise HTTPException(
            status_code=400,
            detail=f"Run explanation is only available for failed runs (status: {run.status}).",
        )
    graph = (run.version.graph_json if run.version else None) or {}
    try:
        return assist_service.explain_run(run, graph)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — LLM/transport failure
        raise HTTPException(
            status_code=502, detail="Run explanation failed. Please try again."
        ) from exc


@router.post("/edit-graph", response_model=EditGraphResponse)
def edit_graph(
    payload: EditGraphRequest,
    user_id: UUID = Depends(get_current_user_id),
) -> EditGraphResponse:
    _require_api_key()
    assist_service.check_assist_rate_limit(str(user_id), "edit")
    try:
        return assist_service.edit_graph(
            payload.graph, payload.instruction, payload.history
        )
    except AssistError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — LLM/transport failure
        raise HTTPException(
            status_code=502, detail="Graph edit failed. Please try again."
        ) from exc


@router.post("/compare", response_model=CompareResponse)
async def compare(
    payload: CompareRequest,
    user_id: UUID = Depends(get_current_user_id),
) -> CompareResponse:
    # No _require_api_key here: compare degrades gracefully (per-variant error,
    # HTTP 200) when the key is unset, so the frontend still gets a shaped result.
    assist_service.check_assist_rate_limit(str(user_id), "compare")
    results = await assist_service.compare_variants(payload)
    return CompareResponse(results=results)


@router.post("/generate-schema", response_model=GenerateSchemaResponse)
def generate_schema(
    payload: GenerateSchemaRequest,
    user_id: UUID = Depends(get_current_user_id),
) -> GenerateSchemaResponse:
    _require_api_key()
    assist_service.check_assist_rate_limit(str(user_id), "schema")
    try:
        return assist_service.generate_schema(payload.description, payload.kind)
    except AssistError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — LLM/transport failure
        raise HTTPException(status_code=502, detail=f"Schema generation failed: {exc}") from exc
