"""HTTP endpoints of M11. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import PlanRequest, PlanResponse

router = APIRouter(prefix="/m11", tags=["M11 Trip planner"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/plan", response_model=PlanResponse)
def plan(req: PlanRequest):
    return _impl().plan(req.model_dump())
