"""HTTP endpoints of M18. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import AdviseRequest, AdviseResponse

router = APIRouter(prefix="/m18", tags=["M18 Size & fit advice"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/advise", response_model=AdviseResponse)
def advise(req: AdviseRequest):
    return _impl().advise(req.model_dump())

@router.get("/identity")
def identity_card():
    from .identity import CARD
    return CARD
