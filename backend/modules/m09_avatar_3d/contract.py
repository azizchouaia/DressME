"""M9 input / output. Agree them on day 1, change only through a PR reviewed by the owner."""

from typing import Literal

from pydantic import BaseModel, Field


class RenderRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class RenderResponse(BaseModel):
    result: dict = {}
    mocked: bool = True


class NextAction(BaseModel):
    action: str
    label: str
    tool: str | None = None
    args: dict = Field(default_factory=dict)


class TryOnInput(BaseModel):
    user_id: str
    session_id: str = "default"
    language: Literal["en", "fr", "ar"] = "en"
    message: str = ""
    pose: str | None = None
    garments: list[str] = Field(default_factory=list)
    answer: str | None = None


class TryOnOutput(BaseModel):
    body: str
    pose: str
    garments: list[str]
    question: str | None = None
    next_actions: list[NextAction] = Field(default_factory=list)
    agent: str = "tryon"
    decision_id: str = ""
    mocked: bool = False
