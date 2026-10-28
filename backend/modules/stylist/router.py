"""HTTP endpoints of the Stylist agent. Included automatically by api/main.py."""

from fastapi import APIRouter

from .agent import agent

router = APIRouter(prefix="/stylist", tags=["Stylist agent (BO1 / BO2, LLM)"])


@router.post("/chat")
async def chat(req: dict):
    """{"user_id", "payload": {"message", "session_id", "show_on_avatar"}} -> reply + outfits + trace."""
    return await agent(
        {
            "action": "chat",
            "user_id": req.get("user_id"),
            "payload": req.get("payload") or {},
            "sender": "http",
        }
    )


@router.get("/memory")
async def memory(user_id: str = "anonymous", session_id: str = "default"):
    return await agent({"action": "memory", "user_id": user_id, "payload": {"session_id": session_id}})


@router.delete("/memory")
async def forget(user_id: str = "anonymous", session_id: str | None = None):
    return await agent({"action": "forget", "user_id": user_id, "payload": {"session_id": session_id}})


@router.get("/status")
async def status():
    return await agent({"action": "status"})
