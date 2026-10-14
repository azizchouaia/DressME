"""Local test UI for BO5 Smart Buy.

Run from backend/ (venv active):
    pip install fastapi uvicorn python-multipart
    pip install torch transformers pillow        # only for photo analysis
    uvicorn bo.bo5_purchase.demo.app:app --reload --port 8005
Open http://localhost:8005
"""

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from modules.m06_smartbuy import goals as goals_mod, synthetic as syn, vision
from modules.m06_smartbuy.shopping import shopping_list
from bo.bo5_purchase import closet
from modules.m06_smartbuy.agent import SmartBuyAgent
from modules.m06_smartbuy.contract import SmartBuyInput

app = FastAPI(title="DressMe · Smart Buy (BO5) test UI")
agent = SmartBuyAgent()
PAGE = Path(__file__).with_name("index.html")


def _sync_closet():
    agent.clients.wardrobes[closet.USER] = closet.load()


_sync_closet()


def _strip(it: dict) -> dict:
    return {k: v for k, v in it.items() if k != "embedding"}


async def _analyze(file: UploadFile) -> tuple[bytes, dict]:
    data = await file.read()
    if not data:
        raise HTTPException(400, "empty file")
    try:
        ai = vision.analyze(data)
    except vision.VisionUnavailable as e:
        raise HTTPException(503, str(e)) from e
    except Exception as e:  # unreadable image, model error
        raise HTTPException(400, f"could not analyse the image: {e}") from e
    return data, ai


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE.read_text(encoding="utf-8")


@app.get("/api/meta")
def meta():
    cl = agent.clients
    return {
        "users": [{"id": u, "items": len(w["items"]), "gaps": w.get("gaps", [])} for u, w in cl.wardrobes.items()],
        "candidates": [_strip({**c, "user_id": c.get("user_id", "usr_demo"), "price_tnd": c.get("price_tnd", 80)})
                       for c in cl.candidates.values()],
        "types": {s: {"category": v[0], "price": v[2], "colours": syn.TYPE_COLOURS[s]} for s, v in syn.TYPES.items()},
        "colours": {c: v[0] for c, v in syn.COLOURS.items()},
        "brands": [b for b, v in agent.charts.items() if isinstance(v, dict)],
        "goal_templates": {k: {"name": t["name"], "description": t["description"]} for k, t in goals_mod.TEMPLATES.items()},
        "config": {**{k: agent.config[k] for k in ("buy_threshold", "skip_threshold", "duplicate_threshold", "max_same_type")},
                   "decision": "learned" if agent.model else "rules", "personalize": bool(agent.bandit)},
    }


@app.get("/api/wardrobe/{user_id}")
def wardrobe(user_id: str):
    w = agent.clients.wardrobes.get(user_id)
    if not w:
        raise HTTPException(404, "unknown user")
    return {"user_id": user_id, "gaps": w.get("gaps", []), "items": [_strip(i) for i in w["items"]]}


@app.post("/api/verdict")
async def verdict(inp: SmartBuyInput):
    try:
        return await agent(inp.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# ---------------- personal goals (mock of M5) + shopping list
class Goals(BaseModel):
    templates: list[str] = []
    budget: dict = {}


@app.get("/api/goals/{user_id}")
def get_goals(user_id: str):
    return agent.clients.goals(user_id)


@app.put("/api/goals/{user_id}")
def put_goals(user_id: str, g: Goals):
    bad = [t for t in g.templates if t not in goals_mod.TEMPLATES]
    if bad:
        raise HTTPException(400, f"unknown goal(s): {bad}")
    return agent.clients.set_goals(user_id, g.model_dump())


@app.get("/api/shopping-list/{user_id}")
def get_shopping_list(user_id: str):
    try:
        return {"goals": agent.clients.goals(user_id), "items": shopping_list(agent, user_id)}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


# ---------------- feedback -> bandit (idea 9)
class Feedback(BaseModel):
    user_id: str
    offset: int = 0
    good: bool


@app.post("/api/feedback")
def feedback(fb: Feedback):
    if not agent.bandit:
        return {"personalize": False}
    agent.bandit.update(fb.user_id, fb.offset, fb.good)
    return {"personalize": True, "best": agent.bandit.best(fb.user_id)}


# ---------------- photo analysis (local stand-in for M1 /classify)
@app.post("/api/analyze")
async def analyze(file: UploadFile = File(...)):
    _, ai = await _analyze(file)
    return {k: v for k, v in ai.items() if k != "clip_embedding"}


# ---------------- my closet (usr_me)
class Fix(BaseModel):
    subcategory: str
    colour: str


class Gaps(BaseModel):
    gaps: list[str]


@app.post("/api/closet")
async def closet_add(file: UploadFile = File(...)):
    data, ai = await _analyze(file)
    it = closet.add(data, Path(file.filename or "x.jpg").suffix, ai)
    _sync_closet()
    return _strip(it)


@app.patch("/api/closet/{item_id}")
def closet_fix(item_id: str, fix: Fix):
    if fix.subcategory not in syn.TYPES or fix.colour not in syn.COLOURS:
        raise HTTPException(400, "unknown type or colour")
    try:
        it = closet.correct(item_id, fix.subcategory, fix.colour)
    except KeyError as e:
        raise HTTPException(404, "unknown item") from e
    _sync_closet()
    return _strip(it)


@app.delete("/api/closet/{item_id}", status_code=204)
def closet_remove(item_id: str):
    closet.remove(item_id)
    _sync_closet()


@app.put("/api/closet/gaps")
def closet_gaps(g: Gaps):
    w = closet.set_gaps(g.gaps)
    _sync_closet()
    return {"gaps": w["gaps"]}


@app.get("/api/closet/image/{name}")
def closet_image(name: str):
    p = (closet.IMAGES / name).resolve()
    if p.parent != closet.IMAGES.resolve() or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)
