"""M3 input / output. Agree them on day 1, change only through a PR reviewed by the owner."""

from pydantic import BaseModel

class WornRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class WornResponse(BaseModel):
    result: dict = {}
    mocked: bool = True

class StatsRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class StatsResponse(BaseModel):
    result: dict = {}
    mocked: bool = True
