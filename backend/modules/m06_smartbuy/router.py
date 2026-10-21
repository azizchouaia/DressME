"""HTTP endpoints of M6 Smart Buy. Included automatically by api/main.py."""

from fastapi import APIRouter, HTTPException

from .agent import SmartBuyAgent
from .contract import SmartBuyInput, SmartBuyOutput

router = APIRouter(prefix="/m06", tags=["M6 Smart Buy / what-if engine"])


@router.get("/identity")
def identity_card():
    from .identity import CARD
    return CARD
_agent = None


def agent() -> SmartBuyAgent:
    global _agent
    if _agent is None:
        _agent = SmartBuyAgent()
    return _agent


@router.post("/verdict", response_model=SmartBuyOutput)
async def verdict(inp: SmartBuyInput):
    try:
        return await agent()(inp.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/shopping-list")
def shopping_list(user_id: str):
    """Wardrobe gap shopping list from the user's goals (M5) + gaps: most useful pieces first."""
    from .shopping import shopping_list as build
    try:
        return {"items": build(agent(), user_id)}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
