"""HTTP endpoints of M14. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import ClientsRequest, ClientsResponse

router = APIRouter(prefix="/m14", tags=["M14 Stylist / boutique mode"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/clients", response_model=ClientsResponse)
def clients(req: ClientsRequest):
    return _impl().clients(req.model_dump())
