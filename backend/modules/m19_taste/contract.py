"""Input and output for the shared taste agent."""

from pydantic import BaseModel, Field


class TasteInput(BaseModel):
    user_id: str = "ada"
    session_id: str = ""
    purpose: str = "outfit"
    candidates: list[dict] = Field(default_factory=list)
    kind: str = ""
    id: str = ""
    title: str = ""
    vector: list[float] = Field(default_factory=list)
    labels: list[str] = Field(default_factory=list)
    fit: str = ""
    gender: str = ""


class TasteOutput(BaseModel):
    purpose: str = "outfit"
    adapted: bool = False
    tastes: int = 0
    score: int = 0
    verdict: str = "wear"
    items: list[dict] = Field(default_factory=list)
    next_actions: list = Field(default_factory=list)
    session_id: str = ""
