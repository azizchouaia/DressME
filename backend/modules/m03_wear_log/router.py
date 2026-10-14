"""HTTP endpoints of M3. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import WornRequest, WornResponse, StatsRequest, StatsResponse

router = APIRouter(prefix="/m03", tags=["M3 Wear log + item status"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/worn", response_model=WornResponse)
def worn(req: WornRequest):
    return _impl().worn(req.model_dump())

@router.post("/stats", response_model=StatsResponse)
def stats(req: StatsRequest):
    return _impl().stats(req.model_dump())
