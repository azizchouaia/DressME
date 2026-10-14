"""HTTP endpoints of M10. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import CardRequest, CardResponse

router = APIRouter(prefix="/m10", tags=["M10 Share / export cards"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/card", response_model=CardResponse)
def card(req: CardRequest):
    return _impl().card(req.model_dump())
