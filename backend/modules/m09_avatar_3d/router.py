"""HTTP endpoints of M9. Included automatically by api/main.py."""

from fastapi import APIRouter

from . import service
from .agent import TryOnAgent
from .contract import RenderRequest, RenderResponse, TryOnInput

router = APIRouter(prefix="/m09", tags=["M9 3D avatar renderer"])


def _impl():
    return service

@router.post("/render", response_model=RenderResponse)
def render(req: RenderRequest):
    return _impl().render(req.model_dump())

@router.post("/run")
async def run(req: TryOnInput):
    return await TryOnAgent()(req.model_dump())


@router.get("/identity")
def identity_card():
    from .identity import CARD
    return CARD
