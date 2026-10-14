"""HTTP endpoints of M17. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import CapsuleRequest, CapsuleResponse

router = APIRouter(prefix="/m17", tags=["M17 Capsule engine"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/capsule", response_model=CapsuleResponse)
def capsule(req: CapsuleRequest):
    return _impl().capsule(req.model_dump())
