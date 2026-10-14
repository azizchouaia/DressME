"""HTTP endpoints of M7. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import SearchRequest, SearchResponse

router = APIRouter(prefix="/m07", tags=["M7 Local catalogue"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest):
    return _impl().search(req.model_dump())
