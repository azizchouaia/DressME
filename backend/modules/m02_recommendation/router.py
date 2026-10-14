"""HTTP endpoints of M2. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import RecommendRequest, RecommendResponse

router = APIRouter(prefix="/m02", tags=["M2 Recommendation engine"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/recommend", response_model=RecommendResponse)
def recommend(req: RecommendRequest):
    return _impl().recommend(req.model_dump())
