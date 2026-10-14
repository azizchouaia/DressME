"""M12 input / output. Agree them on day 1, change only through a PR reviewed by the owner."""

from pydantic import BaseModel

class TimelineRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class TimelineResponse(BaseModel):
    result: dict = {}
    mocked: bool = True
