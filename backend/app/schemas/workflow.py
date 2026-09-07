from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WorkflowCreate(BaseModel):
    name: str
    description: str | None = None
    graph_json: dict = Field(default_factory=lambda: {"nodes": [], "edges": []})


class WorkflowImportPayload(BaseModel):
    """Accepts full aegis-workflow-v1 export JSON or a partial payload with graph_json."""

    format: str | None = None
    name: str | None = None
    description: str | None = None
    graph_json: dict | None = None
    workflow_id: str | None = None
    version_number: int | None = None
    version_id: str | None = None
    exported_at: str | None = None

    model_config = {"extra": "ignore"}


class WorkflowImportIntoExisting(BaseModel):
    format: str | None = None
    name: str | None = None
    description: str | None = None
    graph_json: dict | None = None
    workflow_id: str | None = None
    version_number: int | None = None
    version_id: str | None = None
    exported_at: str | None = None
    save_as_new_version: bool = True

    model_config = {"extra": "ignore"}


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    webhook_url: str | None = None
    budget_json: dict | None = None


class WorkflowTriggerPayload(BaseModel):
    """Inbound webhook body — mapped to workflow input (Lyzr Input / n8n trigger)."""
    input: dict | str | None = None


class WorkflowVersionCreate(BaseModel):
    graph_json: dict
    save_as_new_version: bool = False


class WorkflowVersionResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    version_number: int
    graph_json: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowVersionListItem(BaseModel):
    id: UUID
    workflow_id: UUID
    version_number: int
    created_at: datetime
    node_count: int = 0

    model_config = {"from_attributes": True}


class WorkflowResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    webhook_url: str | None = None
    created_at: datetime
    updated_at: datetime
    latest_version: WorkflowVersionResponse | None = None

    model_config = {"from_attributes": True}


class RunCompareResponse(BaseModel):
    run_a_id: UUID
    run_b_id: UUID
    run_a_scores: dict | None = None
    run_b_scores: dict | None = None
    delta: dict[str, float | None] = {}
    run_a_output: str | None = None
    run_b_output: str | None = None
    run_a_version: int | None = None
    run_b_version: int | None = None


class WorkflowListItem(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    version_count: int = 0
    latest_version_number: int | None = None
    published: bool = False
    is_external: bool = False

    model_config = {"from_attributes": True}


class ScheduledWorkflowInfo(BaseModel):
    workflow_id: str
    workflow_name: str
    cron: str
    cron_valid: bool = True
    next_run_at: str | None = None
    next_runs: list[str] = []
    last_fired_at: str | None = None


class GuardrailPreviewRequest(BaseModel):
    text: str
    rules: dict = Field(default_factory=dict)


class GuardrailPreviewResponse(BaseModel):
    passed: bool
    message: str
    severity: str = "ok"
    would_block: bool = False