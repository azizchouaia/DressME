"""HTTP endpoints of M13. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import LinksRequest, LinksResponse

router = APIRouter(prefix="/m13", tags=["M13 Partner commerce links"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/links", response_model=LinksResponse)
def links(req: LinksRequest):
    return _impl().links(req.model_dump())
