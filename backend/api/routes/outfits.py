"""Owner: M2"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/today")
async def outfit_of_the_day():
    """Weather + Profile + Stylist agents."""
    raise NotImplementedError


@router.post("/feedback")
async def feedback():
    """Swipe accept/reject -> Event -> Profile agent."""
    raise NotImplementedError
