"""HTTP endpoints of M15. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import ChallengesRequest, ChallengesResponse

router = APIRouter(prefix="/m15", tags=["M15 Community challenges"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/challenges", response_model=ChallengesResponse)
def challenges(req: ChallengesRequest):
    return _impl().challenges(req.model_dump())
