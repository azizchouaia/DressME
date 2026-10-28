"""Test web app of the BO1 / BO2 agents: /bo/demo.

GET  /bo/demo                 the page (chat with the BO agents or any idea agent, pipeline, agent cards)
GET  /bo/agents               cards of the BO1 / BO2 idea agents and orchestrators
GET  /bo/catalog?user_id=     piece id -> {name, image} (to show outfits as pictures)
POST /bo/chat                 {agent, user_id, session_id, message, payload?} -> the agent's AgentResult
POST /bo/upload               photo of a piece -> server path (for the photo_piece agent)
DELETE /bo/memory?user_id=    forget the conversation / session state (taste profile kept unless all=true)
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

router = APIRouter(prefix="/bo", tags=["BO1 / BO2 agents"])
PAGE = Path(__file__).resolve().parents[2] / "bo" / "demo.html"
UPLOADS = Path(__file__).resolve().parents[2] / "bo" / ".uploads"
BO_AGENTS = ("personalised_recommendations", "time_optimisation")


class ChatIn(BaseModel):
    agent: str = "personalised_recommendations"
    user_id: str = "demo_f"
    session_id: str = "web"
    message: str = ""
    payload: dict = {}


@router.get("/demo", include_in_schema=False)
def page():
    return FileResponse(PAGE)


@router.get("/screens", include_in_schema=False)
def screens():
    """App-like screens: buttons call the agents directly (no LLM) and the page draws who calls whom."""
    return FileResponse(PAGE.parent / "screens.html")


@router.get("/agents")
def agents():
    from shared import agent_bus
    from shared.idea_agent import IdeaAgent

    out = []
    for a in agent_bus.agents().values():
        if isinstance(a, IdeaAgent):
            c = a.card()
            out.append(
                {
                    "name": c["name"],
                    "owner": c["owner"],
                    "role": c["role"],
                    "ideas": c.get("ideas"),
                    "module": c["module"],
                    "skills": c.get("skills"),
                    "examples": c.get("when_to_use"),
                    "orchestrator": c["name"] in BO_AGENTS,
                    "actions": {k: v for k, v in c["actions"].items() if "." not in k},
                }
            )
    return {"agents": out}


@router.get("/catalog")
async def catalog(user_id: str = "demo_f"):
    from shared.wardrobe import catalog as cat

    c = await cat(user_id)
    images = {}
    if c["source"].startswith("my wardrobe"):
        for g in c["m2_items"]:
            images[g["item_id"]] = g.get("image_cutout") or g.get("image_raw")
    elif c["source"].startswith("my 3D"):
        from modules.m09_avatar_3d import wardrobe3d

        for p in wardrobe3d.state(user_id)["pieces"]:
            images[p["piece_id"]] = p.get("cutout_url") or p.get("front_url")
    elif c["items"]:
        from modules.m02_recommendation import service as m2

        who = user_id if user_id.startswith("demo_") else "demo_f"
        for it in m2.demo_wardrobe(who)["items"]:
            images[it["item_id"]] = it.get("image")
    return {
        "source": c["source"],
        "pieces": {
            it["id"]: {"name": it["name"], "category": it["category"], "image": images.get(it["id"])}
            for it in c["items"]
        },
    }


@router.post("/chat")
async def chat(req: ChatIn):
    from shared import agent_bus

    try:
        agent = agent_bus.get(req.agent)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    return await agent(
        {"user_id": req.user_id, "session_id": req.session_id, "message": req.message, "payload": req.payload}
    )


@router.post("/upload")
async def upload(photo: UploadFile = File(...)):  # noqa: B008
    UPLOADS.mkdir(parents=True, exist_ok=True)
    ext = (Path(photo.filename or "").suffix or ".jpg").lower()
    path = UPLOADS / f"{uuid.uuid4().hex[:12]}{ext}"
    path.write_bytes(await photo.read())
    return {"path": str(path)}


@router.delete("/memory")
def forget(user_id: str = "demo_f", session_id: str = "web", all: bool = False):  # noqa: A002
    from shared import agent_memory, idea_agent

    agent_memory.forget(user_id, None if all else session_id)
    f = idea_agent._state_file(agent_memory._safe(user_id, "anonymous"), session_id)
    if f.exists():
        f.unlink()
    return {"forgotten": True}
