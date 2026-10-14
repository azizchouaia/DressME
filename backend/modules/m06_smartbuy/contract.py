"""M6 input / output. Agree them on day 1, change only through a PR reviewed by the owner."""

from pydantic import BaseModel

class VerdictRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class VerdictResponse(BaseModel):
    result: dict = {}
    mocked: bool = True
