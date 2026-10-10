"""Owner: M6"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/message")
async def message():
    """Send the message to the orchestrator graph."""
    raise NotImplementedError
