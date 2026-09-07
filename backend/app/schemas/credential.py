from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CredentialCreate(BaseModel):
    name: str
    type: str = Field(pattern=r"^(slack|discord|email|postgres)$")
    config: dict = Field(default_factory=dict)


class CredentialResponse(BaseModel):
    id: UUID
    name: str
    type: str
    config: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CredentialListItem(BaseModel):
    id: UUID
    name: str
    type: str
    config: dict
    created_at: datetime

    model_config = {"from_attributes": True}