"""HTTP endpoints of M8. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import ExplainRequest, ExplainResponse, ParseRequest, ParseResponse

router = APIRouter(prefix="/m08", tags=["M8 LLM layer"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/parse", response_model=ParseResponse)
def parse(req: ParseRequest):
    return _impl().parse(req.model_dump())

@router.post("/explain", response_model=ExplainResponse)
def explain(req: ExplainRequest):
    return _impl().explain(req.model_dump())


@router.post("/recommend", response_model=ParseResponse)
def recommend(req: ParseRequest):
    impl = _impl()
    if not hasattr(impl, "recommend"):
        return {"result": {"todo": "M8 recommend mock"}, "mocked": True}
    return impl.recommend(req.model_dump())


@router.post("/chat", response_model=ParseResponse)
def chat(req: ParseRequest):
    impl = _impl()
    if not hasattr(impl, "chat"):
        return {"result": {"todo": "M8 chat mock"}, "mocked": True}
    return impl.chat(req.model_dump())
