"""HTTP endpoints of M4. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import ScheduleRequest, ScheduleResponse, CalendarRequest, CalendarResponse

router = APIRouter(prefix="/m04", tags=["M4 Scheduler, notifications + outfit calendar"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/schedule", response_model=ScheduleResponse)
def schedule(req: ScheduleRequest):
    return _impl().schedule(req.model_dump())

@router.post("/calendar", response_model=CalendarResponse)
def calendar(req: CalendarRequest):
    return _impl().calendar(req.model_dump())

@router.get("/identity")
def identity_card():
    from .identity import CARD
    return CARD
