"""HTTP endpoints of M7. Included automatically by api/main.py.

M7 is implemented, so the router always serves service.py (mock.py stays for other BOs' offline tests).
"""

import asyncio
import re
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse

from shared.base_agent import AgentError

from . import events, service
from .contract import ClickEvent, Feedback, LocalShopInput, LocalShopOutput
from .identity import CARD
from .paths import CONFIG, IMAGES_DIR

_IMAGE_NAME = re.compile(r"[0-9a-f]{16}\.jpg")  # names written by scraper/images.py, nothing else


@asynccontextmanager
async def _warm_up(app: FastAPI):
    """Load the catalogue and FashionCLIP as soon as the API starts (config.yaml warm_up), so the
    first search does not wait ~13 s for them."""
    task = None
    if CONFIG.get("warm_up") and service.knowledge_base_ready():
        task = asyncio.create_task(service.get_agent())
    yield
    if task is not None and not task.done():
        task.cancel()


router = APIRouter(prefix="/m07", tags=["M7 Local catalogue"], lifespan=_warm_up)


@router.post("/search", response_model=LocalShopOutput)
async def search(body: LocalShopInput):
    """'baskets blanches à Tunis max 80 TND', a gap from Smart Buy, a photo embedding or a style vector."""
    try:
        return await service.search(body.model_dump())
    except AgentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/card")
async def card():
    """Agent card: identity, skills, when to use, contract. Read by the orchestrator / other agents."""
    return CARD


@router.get("/identity")
async def identity_card():
    """Same card, at the path the orchestrator branch (BO8) reads."""
    return CARD


@router.post("/feedback")
async def feedback(body: Feedback):
    """Were the results of a search useful / did the user buy one? (decision_id from the search output)"""
    try:
        return service.feedback(body.user_id, body.decision_id, body.useful, body.bought_product_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/history/{user_id}")
async def history(user_id: str, n: int = 10):
    """Past searches of this user (long-term memory)."""
    return {"history": service.memory().history(user_id, n)}


@router.delete("/memory/{user_id}", status_code=204)
async def forget(user_id: str):
    """Forget everything localshop remembers about this user (privacy)."""
    service.memory().forget(user_id)


@router.post("/events", status_code=204)
async def click(body: ClickEvent):
    """The app reports that a result was opened or that the user went to the shop (logged for M14)."""
    events.log_click(body.type, body.product_id, body.search_id, body.shop, body.rank, body.user_id)


@router.get("/shops")
async def shops():
    """Shops in the catalogue with their city, product count and website."""
    return await service.shops()


@router.get("/products/{product_id}")
async def product(product_id: str):
    found = await service.product(product_id)
    if found is None:
        raise HTTPException(status_code=404, detail="unknown product_id")
    return found


@router.get("/images/{name}")
async def image(name: str):
    """Local copy of a product photo (result field image_path = "images/<name>"), served by DressMe so the
    app does not depend on the shops' websites."""
    path = IMAGES_DIR / name
    if not _IMAGE_NAME.fullmatch(name) or not path.is_file():
        raise HTTPException(status_code=404, detail="unknown image")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})
