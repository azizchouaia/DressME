"""HTTP endpoints of M5. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import ProfileRequest, ProfileResponse, FeedbackRequest, FeedbackResponse, GapsRequest, GapsResponse

router = APIRouter(prefix="/m05", tags=["M5 Adaptive style profile"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/profile", response_model=ProfileResponse)
def profile(req: ProfileRequest):
    return _impl().profile(req.model_dump())

@router.post("/feedback", response_model=FeedbackResponse)
def feedback(req: FeedbackRequest):
    return _impl().feedback(req.model_dump())

@router.post("/gaps", response_model=GapsResponse)
def gaps(req: GapsRequest):
    return _impl().gaps(req.model_dump())

@router.get("/identity")
def identity_card():
    from .identity import CARD
    return CARD
