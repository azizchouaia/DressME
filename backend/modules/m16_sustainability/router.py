"""HTTP endpoints of M16. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import ScoreRequest, ScoreResponse

router = APIRouter(prefix="/m16", tags=["M16 Sustainability / cost-per-wear score"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest):
    return _impl().score(req.model_dump())
