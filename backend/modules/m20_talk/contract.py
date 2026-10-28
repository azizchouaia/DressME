"""Input and output for the talk agent."""

from pydantic import BaseModel, Field


class TalkInput(BaseModel):
    user_id: str = "ada"
    session_id: str = ""
    message: str = ""
    candidates: list[dict] = Field(default_factory=list)


class TalkOutput(BaseModel):
    reply: str
    loves: list[str] = Field(default_factory=list)
    avoids: list[str] = Field(default_factory=list)
    wardrobe: list[str] = Field(default_factory=list)
    scores: dict[str, int] = Field(default_factory=dict)
    remembered: list[str] = Field(default_factory=list)
    next_actions: list = Field(default_factory=list)
    session_id: str = ""
