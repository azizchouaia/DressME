"""HTTP endpoints of M6 Smart Buy. Included automatically by api/main.py."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

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


@router.post("/shopping-list")
def shopping_list(user_id: str):
    """Wardrobe gap shopping list from the user's goals (M5) + gaps: most useful pieces first."""
    from .shopping import shopping_list as build
    try:
        return {"items": build(agent(), user_id)}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/card")
def card():
    """Agent card: identity, skills, when to use, contract. Read by the orchestrator / other agents."""
    return agent().card()


class FeedbackIn(BaseModel):
    user_id: str
    decision_id: str
    bought: bool | None = None
    liked: bool | None = None


@router.post("/feedback")
def feedback(fb: FeedbackIn):
    """Did the user buy it / was the advice good? -> memory + personal strictness."""
    try:
        return agent().feedback(fb.user_id, fb.decision_id, fb.bought, fb.liked)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/history/{user_id}")
def history(user_id: str, n: int = 10):
    """Past verdicts of this user (long-term memory)."""
    return {"history": agent().memory.history(user_id, n)}


@router.delete("/memory/{user_id}", status_code=204)
def forget(user_id: str):
    """Forget everything Smart Buy remembers about this user (privacy)."""
    agent().memory.forget(user_id)


@router.get("/meta")
def meta():
    """What the app needs to draw the Smart Buy screen: demo users, piece types + colours, shop brands."""
    from . import synthetic as syn
    a = agent()
    return {
        "users": [{"id": u, "items": len(w["items"])} for u, w in a.clients.wardrobes.items()],
        "types": {s: {"category": v[0], "colours": syn.TYPE_COLOURS[s]} for s, v in syn.TYPES.items()},
        "colours": {c: v[0] for c, v in syn.COLOURS.items()},
        "brands": [b for b, v in a.charts.items() if isinstance(v, dict)],
    }


class PhotoIn(BaseModel):
    image: str  # data URL or base64


@router.post("/analyze")
def analyze(p: PhotoIn):
    """Photo -> type + colour (FashionCLIP + pixel colour), for the user to confirm before the verdict."""
    import base64
    from . import vision
    raw = p.image.split(",", 1)[1] if p.image.startswith("data:") else p.image
    try:
        ai = vision.analyze(base64.b64decode(raw))
    except vision.VisionUnavailable as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:  # noqa: BLE001 - unreadable image
        raise HTTPException(400, f"could not read the photo: {e}") from e
    return {k: v for k, v in ai.items() if k != "clip_embedding"}


@router.get("/identity")
def identity_card():
    from .identity import CARD
    return CARD
