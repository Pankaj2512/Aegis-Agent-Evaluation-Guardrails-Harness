from pydantic import BaseModel, Field


class RouterDecision(BaseModel):
    route: str = Field(description="Selected route key")
    reasoning: str = ""


class ClassifierDecision(BaseModel):
    route: str = Field(description="Selected category key (used as branch route)")
    reasoning: str = ""