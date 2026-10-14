"""HTTP endpoints of M9. Included automatically by api/main.py."""

from fastapi import APIRouter

from shared.config import settings

from . import mock, service
from .contract import RenderRequest, RenderResponse

router = APIRouter(prefix="/m09", tags=["M9 3D avatar renderer"])


def _impl():
    return mock if getattr(settings, "use_mocks", True) else service

@router.post("/render", response_model=RenderResponse)
def render(req: RenderRequest):
    return _impl().render(req.model_dump())
