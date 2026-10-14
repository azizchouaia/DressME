"""HTTP endpoints of M6 Smart Buy. Included automatically by api/main.py."""

from fastapi import APIRouter, HTTPException

from .agent import SmartBuyAgent
from .contract import SmartBuyInput, SmartBuyOutput

router = APIRouter(prefix="/m06", tags=["M6 Smart Buy / what-if engine"])
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
