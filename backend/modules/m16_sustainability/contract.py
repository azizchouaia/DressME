"""M16 input / output. Agree them on day 1, change only through a PR reviewed by the owner."""

from pydantic import BaseModel

class ScoreRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class ScoreResponse(BaseModel):
    result: dict = {}
    mocked: bool = True
