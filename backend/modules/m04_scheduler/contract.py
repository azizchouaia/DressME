"""M4 input / output. Agree them on day 1, change only through a PR reviewed by the owner."""

from pydantic import BaseModel

class ScheduleRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class ScheduleResponse(BaseModel):
    result: dict = {}
    mocked: bool = True

class CalendarRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class CalendarResponse(BaseModel):
    result: dict = {}
    mocked: bool = True
