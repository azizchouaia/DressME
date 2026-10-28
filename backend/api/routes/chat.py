"""BO8 chat gateway: the app talks to ONE endpoint; the orchestrator picks the agents.

POST /chat/message   {user_id, session_id, message}  -> reply, question, next_actions, cards, last_agent
GET  /chat/agents    every agent's card (what the assistant can do)
GET  /chat/status    is the LLM up, which agents are tools
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()
_graph = None


def graph():
    global _graph
    if _graph is None:
        from orchestrator.graph import build_graph

        _graph = build_graph(model=brain())
    return _graph


def brain():
    """The planner/writer LLM: LLM_PROVIDER from infra/.env when it is set up, else the team's local Ollama model."""
    from shared.config import settings

    if settings.llm_provider in ("anthropic", "openai") and not settings.llm_api_key:
        import os

        from langchain_ollama import ChatOllama

        return ChatOllama(model=os.environ.get("OLLAMA_MODEL", "llama3.1:8b"), temperature=0.2,
                          base_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    from shared.llm import get_chat_model

    return get_chat_model()


class ChatIn(BaseModel):
    user_id: str = "usr_demo"
    session_id: str = "default"
    message: str = Field(min_length=1)


class ChatOut(BaseModel):
    reply: str
    question: str | None = None
    next_actions: list[dict] = []
    cards: list[dict] = []
    session_id: str
    last_agent: str | None = None


@router.post("/message", response_model=ChatOut)
async def message(inp: ChatIn):
    """One user message -> the orchestrator (planner -> agent -> writer). Same session_id = same conversation."""
    from orchestrator.graph import run_turn

    try:
        out = await run_turn(graph(), user_id=inp.user_id, session_id=inp.session_id, message=inp.message)
    except Exception as e:  # noqa: BLE001 - LLM down / misconfigured: say it clearly
        raise HTTPException(503, f"assistant unavailable: {type(e).__name__}: {e}. "
                                 "Is Ollama running with the model in LLM_MODEL (default llama3.1:8b)?") from e
    return out


@router.get("/agents")
def agents():
    from orchestrator.registry import cards

    return {"agents": cards()}


@router.get("/status")
def status():
    from orchestrator.registry import tool_names
    from shared.config import settings
    from shared.local_llm import available

    b = brain()
    return {"llm": {"brain": type(b).__name__, "model": getattr(b, "model", None) or getattr(b, "model_name", None),
                    "ollama": available()},
            "agents": tool_names()}
