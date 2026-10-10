"""Owner: M1"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/items")
async def add_item():
    """Upload photo -> Vision agent (async job) -> Garment."""
    raise NotImplementedError


@router.get("/items")
async def list_items():
    raise NotImplementedError
