"""M1 input / output. Agree them on day 1, change only through a PR reviewed by the owner."""

from pydantic import BaseModel

class ClassifyRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class ClassifyResponse(BaseModel):
    result: dict = {}
    mocked: bool = True

class SimilarRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class SimilarResponse(BaseModel):
    result: dict = {}
    mocked: bool = True

class ItemsRequest(BaseModel):
    user_id: str | None = None
    payload: dict = {}


class ItemsResponse(BaseModel):
    result: dict = {}
    mocked: bool = True
