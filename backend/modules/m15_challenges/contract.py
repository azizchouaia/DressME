"""M15 input / output. Agree them on day 1, change only through a PR reviewed by the owner."""

from pydantic import BaseModel

class ChallengesRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class ChallengesResponse(BaseModel):
    result: dict = {}
    mocked: bool = True
