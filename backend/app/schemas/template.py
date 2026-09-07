"""Schemas for workflow templates (built-in + user-published)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TemplateItem(BaseModel):
    """A template as returned by GET /api/templates.

    Backward-compatible with the existing frontend listTemplates() shape
    (id/name/description/graph_json); the provenance fields are additive.
    """

    id: str
    name: str
    description: str
    graph_json: dict
    author: str | None = None
    usage_count: int = 0
    created_at: datetime | None = None
    builtin: bool = False


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    workflow_id: UUID


class TemplateUseResponse(BaseModel):
    id: str
    name: str
    graph_json: dict
    usage_count: int
