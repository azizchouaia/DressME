"""HTTP endpoints of M6. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import VerdictRequest, VerdictResponse

router = APIRouter(prefix="/m06", tags=["M6 Smart Buy / what-if engine"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/verdict", response_model=VerdictResponse)
def verdict(req: VerdictRequest):
    return _impl().verdict(req.model_dump())
