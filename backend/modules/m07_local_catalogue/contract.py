"""M7 input / output. Agree them on day 1, change only through a PR reviewed by the owner."""

from pydantic import BaseModel

class SearchRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class SearchResponse(BaseModel):
    result: dict = {}
    mocked: bool = True
