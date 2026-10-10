"""Owner: M4"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/check")
async def check():
    raise NotImplementedError
