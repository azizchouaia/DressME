"""HTTP endpoints of M8. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import ParseRequest, ParseResponse, ExplainRequest, ExplainResponse

router = APIRouter(prefix="/m08", tags=["M8 LLM layer"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/parse", response_model=ParseResponse)
def parse(req: ParseRequest):
    return _impl().parse(req.model_dump())

@router.post("/explain", response_model=ExplainResponse)
def explain(req: ExplainRequest):
    return _impl().explain(req.model_dump())
