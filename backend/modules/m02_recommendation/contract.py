"""M2 input / output. Agree them on day 1, change only through a PR reviewed by the owner."""

from pydantic import BaseModel

class RecommendRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class RecommendResponse(BaseModel):
    result: dict = {}
    mocked: bool = True
