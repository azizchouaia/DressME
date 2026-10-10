"""Owner: M5"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/render")
async def render():
    raise NotImplementedError
