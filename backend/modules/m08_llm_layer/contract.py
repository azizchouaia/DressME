"""M8 input / output. Agree them on day 1, change only through a PR reviewed by the owner."""

from pydantic import BaseModel

class ParseRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class ParseResponse(BaseModel):
    result: dict = {}
    mocked: bool = True

class ExplainRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class ExplainResponse(BaseModel):
    result: dict = {}
    mocked: bool = True
