"""HTTP endpoints of M17. Included automatically by api/main.py."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from shared.config import settings

from . import mock, service
from .contract import CapsuleRequest, CapsuleResponse, PlanRequest

router = APIRouter(prefix="/m17", tags=["M17 Capsule engine"])
DEMO = Path(__file__).parent / "demo"


def _impl():
    """M17_USE_MOCK overrides the global USE_MOCKS for M17 only."""
    flag = os.environ.get("M17_USE_MOCK")
    use_mock = settings.use_mocks if flag is None else flag.lower() in ("1", "true", "yes")
    return mock if use_mock else service


@router.post("/capsule", response_model=CapsuleResponse)
def capsule(req: CapsuleRequest):
    """Choose the N pieces that make the most good outfits (season, occasions, minimums) + a month plan."""
    try:
        return _impl().capsule(req.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/plan", response_model=CapsuleResponse)
def plan(req: PlanRequest):
    """Outfits and a month plan for an existing capsule (its piece ids)."""
    try:
        return _impl().plan_capsule(req.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/demo", include_in_schema=False)
def demo_page():
    return FileResponse(DEMO / "index.html")
