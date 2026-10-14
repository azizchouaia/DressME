"""HTTP endpoints of M12. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import TimelineRequest, TimelineResponse

router = APIRouter(prefix="/m12", tags=["M12 Style evolution tracker"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/timeline", response_model=TimelineResponse)
def timeline(req: TimelineRequest):
    return _impl().timeline(req.model_dump())
