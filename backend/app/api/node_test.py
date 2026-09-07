"""Ephemeral node-test and expression-preview endpoints (canvas authoring aids).

Neither endpoint persists anything: no WorkflowRun/NodeResult rows, no
observability rollups, no SSE. Both operate on the workflow's current
(latest-version) graph and enforce the same optional API-key ownership as the
rest of ``/api/workflows``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user_id
from app.db.database import get_db
from app.schemas.node_test import (
    ExpressionPreviewRequest,
    ExpressionPreviewResponse,
    NodeTestRequest,
    NodeTestResponse,
)
from app.services import node_test as node_test_service

router = APIRouter(prefix="/api/workflows", tags=["node-test"])


@router.post("/{workflow_id}/node-test", response_model=NodeTestResponse)
async def node_test(
    workflow_id: UUID,
    payload: NodeTestRequest,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> NodeTestResponse:
    if len(payload.input_text.encode("utf-8")) > node_test_service.MAX_INPUT_BYTES:
        raise HTTPException(status_code=400, detail="input_text exceeds the 32KB limit.")

    node_test_service.check_node_test_rate_limit(str(user_id))
    node_test_service.get_user_workflow(db, workflow_id, user_id)
    graph = node_test_service.latest_graph(db, workflow_id)

    try:
        result = await node_test_service.run_node_test(
            graph,
            workflow_id,
            user_id,
            payload.node_id,
            payload.input_text,
            payload.extra_context,
            payload.node_data,
        )
    except node_test_service.NodeNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail=f"Node '{payload.node_id}' not found in workflow graph."
        ) from exc

    return NodeTestResponse(**result)


@router.post("/{workflow_id}/expression-preview", response_model=ExpressionPreviewResponse)
def expression_preview(
    workflow_id: UUID,
    payload: ExpressionPreviewRequest,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> ExpressionPreviewResponse:
    if len(payload.expression.encode("utf-8")) > node_test_service.MAX_EXPRESSION_BYTES:
        raise HTTPException(status_code=400, detail="expression exceeds the 8KB limit.")

    node_test_service.get_user_workflow(db, workflow_id, user_id)

    result = node_test_service.preview_expression(
        db,
        workflow_id,
        user_id,
        payload.expression,
        payload.run_id,
        payload.sample_input,
    )
    return ExpressionPreviewResponse(**result)
