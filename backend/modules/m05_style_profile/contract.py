"""M5 input / output. Agree them on day 1, change only through a PR reviewed by the owner."""

from pydantic import BaseModel

class ProfileRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class ProfileResponse(BaseModel):
    result: dict = {}
    mocked: bool = True

class FeedbackRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class FeedbackResponse(BaseModel):
    result: dict = {}
    mocked: bool = True

class GapsRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class GapsResponse(BaseModel):
    result: dict = {}
    mocked: bool = True
