"""Agents over HTTP: the same message as shared.agent_bus.ask, for agents running in other services.

GET  /agents          cards of every module agent (what each one can do, what its actions need)
POST /agents/{name}   {"action", "user_id", "payload", "sender"} -> {"agent", "action", "ok", "result", ...}
"""

from fastapi import APIRouter, HTTPException

from shared import agent_bus
from shared.action_agent import AgentRequest

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("")
def directory():
    return {"agents": agent_bus.directory()}


@router.post("/{name}")
async def call(name: str, req: AgentRequest):
    try:
        agent = agent_bus.get(name)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    return await agent(req.model_dump())
