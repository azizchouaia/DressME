"""HTTP endpoints of M7. Included automatically by api/main.py.

M7 is implemented, so the router always serves service.py (mock.py stays for other BOs' offline tests).
"""

import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from shared.base_agent import AgentError

from . import service
from .contract import LocalShopInput, LocalShopOutput
from .paths import IMAGES_DIR

_IMAGE_NAME = re.compile(r"[0-9a-f]{16}\.jpg")  # names written by scraper/images.py, nothing else

router = APIRouter(prefix="/m07", tags=["M7 Local catalogue"])


@router.post("/search", response_model=LocalShopOutput)
async def search(body: LocalShopInput):
    """'baskets blanches à Tunis max 80 TND', a gap from Smart Buy, a photo embedding or a style vector."""
    try:
        return await service.search(body.model_dump())
    except AgentError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
