from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EvalPresetResponse(BaseModel):
    id: str
    label: str
    criteria: str
    instruction: str | None = None
    score_weights: dict[str, float] | None = None
    source: str = "builtin"
    eval_type: str = "llm"


class EvalPresetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=255)
    criteria: str = Field(min_length=1)
    instruction: str | None = None
    score_weights: dict[str, float] | None = None
    eval_type: str = "llm"


class EvalPresetUpdate(BaseModel):
    label: str | None = Field(default=None, max_length=255)
    criteria: str | None = None
    instruction: str | None = None
    score_weights: dict[str, float] | None = None


class EvalPresetListItem(BaseModel):
    id: UUID
    name: str
    label: str
    criteria: str
    instruction: str | None = None
    score_weights: dict[str, float] | None = None
    eval_type: str
    created_at: datetime
    updated_at: datetime


class EvalPreviewRequest(BaseModel):
    input_text: str = ""
    output_text: str = Field(min_length=1)
    criteria: str | None = None
    instruction: str | None = None
    score_weights: dict[str, float] | None = None


class RagPreviewRequest(BaseModel):
    question: str = ""
    context: str = ""
    answer: str = Field(min_length=1)