from pydantic import BaseModel


class WorkflowMemoryEntry(BaseModel):
    namespace: str
    key: str
    value: str
    updated_at: str | None = None


class WorkflowMemoryResponse(BaseModel):
    workflow_id: str
    entries: list[WorkflowMemoryEntry]
    namespaces: dict[str, dict[str, str]]