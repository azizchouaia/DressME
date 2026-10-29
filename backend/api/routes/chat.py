"""BO8 chat gateway: the app talks to ONE endpoint; the orchestrator picks the agents.

POST /chat/message   {user_id, session_id, message}  -> reply, question, next_actions, cards, last_agent
GET  /chat/agents    every agent's card (what the assistant can do)
GET  /chat/status    is the LLM up, which agents are tools
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()
log = logging.getLogger("dressme.chat")
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
    message: str = ""
    image: str | None = None  # photo of a piece (data URL): read by FashionCLIP, then given to the agent


def _photo(image: str) -> dict:
    """Photo -> what it shows (BO5 vision: FashionCLIP type + pixel colour), for routing and the agents."""
    import base64

    from modules.m06_smartbuy import vision

    raw = image.split(",", 1)[1] if image.startswith("data:") else image
    try:
        g = vision.analyze(base64.b64decode(raw))
        label = f"{g['colour']} {g['subcategory']}"
        return {"image": image, "probe": f"custom:{g['subcategory']}:{g['colour']}", "label": label,
                "subcategory": g["subcategory"], "colour": g["colour"]}
    except Exception as e:  # noqa: BLE001 - vision model missing: the agents still get the photo
        log.warning("photo not read: %s", e)
        return {"image": image, "label": "piece of clothing"}


class ChatOut(BaseModel):
    reply: str
    question: str | None = None
    next_actions: list[dict] = []
    cards: list[dict] = []
    session_id: str
    last_agent: str | None = None
    photo: dict | None = None  # what the photo was read as


@router.post("/message", response_model=ChatOut)
async def message(inp: ChatIn):
    """One user message -> the orchestrator (planner -> agent -> writer). Same session_id = same conversation."""
    from orchestrator.graph import run_turn

    try:
        attachment = _photo(inp.image) if inp.image else None
        message = inp.message.strip()
        if attachment:
            message = (message or "What do you think of this piece?") + f"\n[The user sent a photo of a {attachment['label']}.]"
        if not message:
            raise HTTPException(422, "write a message or send a photo")
        out = await run_turn(graph(), user_id=inp.user_id, session_id=inp.session_id, message=message,
                             attachment=attachment)
        if attachment:
            out["photo"] = {k: attachment.get(k) for k in ("label", "subcategory", "colour")}
    except HTTPException:
        raise
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
