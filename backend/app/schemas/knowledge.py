from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class KnowledgeDocumentCreate(BaseModel):
    title: str | None = None
    text: str = Field(min_length=1)


class KnowledgeBulkImport(BaseModel):
    documents: list[KnowledgeDocumentCreate] = Field(min_length=1, max_length=100)


class KnowledgeDocumentResponse(BaseModel):
    id: UUID
    workflow_id: UUID
    title: str | None
    text: str
    has_embedding: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_row(cls, row) -> "KnowledgeDocumentResponse":
        return cls(
            id=row.id,
            workflow_id=row.workflow_id,
            title=row.title,
            text=row.text,
            has_embedding=bool(row.embedding),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )