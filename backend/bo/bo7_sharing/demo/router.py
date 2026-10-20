"""Owner: BO7 · browser demo of M10 + M15 (dev only). Open http://localhost:8000/bo7/demo

Served by the API itself (same origin), so it works without Flutter and without CORS settings.
"My wardrobe" adds real garment photos, stored in bo/bo7_sharing/demo_wardrobe/ (stand-in for M1).
"""

import base64
import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from bo.bo7_sharing.demo import cutout
from modules.m15_challenges.singleton import challenges_agent

router = APIRouter(prefix="/bo7/demo", tags=["BO7 demo"])
PAGE = Path(__file__).parent / "page.html"
Category = Literal["top", "bottom", "dress", "outerwear", "shoes", "accessory", "traditional"]


def _ward():
    w = challenges_agent.wardrobe
    if not hasattr(w, "save_photo") or not getattr(w, "photos_dir", None):
        raise HTTPException(400, "real photos are only available with the mock wardrobe")
    return w


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def demo_page():
    return PAGE.read_text(encoding="utf-8")


@router.get("/wardrobe")
async def demo_wardrobe(user_id: str = "usr_042"):
    """Garments of the demo wardrobe (stands in for M1 until it is live)."""
    w = challenges_agent.wardrobe
    out = []
    extra = {r["item_id"]: r for r in (w._added() if hasattr(w, "_added") else [])}
    for g in w.items(user_id):
        main = max(g.colors, key=lambda c: c.share) if g.colors else None
        photo = w.photo_path(g.item_id) if hasattr(w, "photo_path") else None
        out.append(
            {
                "item_id": g.item_id,
                "name": g.subcategory or g.category.value,
                "category": g.category.value,
                "color_hex": main.hex if main else "#C9C6CC",
                "color": main.name if main else None,
                "local_tag": g.local_tag,
                "photo_url": f"/bo7/demo/photos/{g.item_id}.png?v={int(photo.stat().st_mtime)}"
                if photo
                else None,
                "image": g.image_cutout,  # local path, passed back to /share/cards by the demo page
                "added": g.item_id in extra,
                "description": extra.get(g.item_id, {}).get("description"),
                "source": extra.get(g.item_id, {}).get("source"),
            }
        )
    return out


class PhotoIn(BaseModel):
    image: str = Field(description="data URI of the photo (jpg, png, webp)")
    item_id: str | None = Field(None, description="existing item to give a photo to; empty = new garment")
    category: Category | None = None
    name: str | None = Field(None, max_length=40)
    local_tag: str | None = Field(None, max_length=40)


@router.post("/wardrobe/items")
async def add_photo(body: PhotoIn):
    """Photo → background removal → crop → K-means colours → saved cutout (demo stand-in for M1)."""
    w = _ward()
    try:
        data = base64.b64decode(body.image.split(",", 1)[-1])
        res = cutout.run(data)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"cannot read this image: {e}") from e

    if body.item_id:
        if not any(g.item_id == body.item_id for g in w.items("usr_042")):
            raise HTTPException(404, "unknown item")
        item_id, meta = body.item_id, None
    else:
        if not body.category:
            raise HTTPException(400, "category is required for a new garment")
        slug = re.sub(r"[^a-z0-9]+", "_", (body.name or body.category).lower()).strip("_")[:20]
        item_id = f"itm_{slug}_{uuid.uuid4().hex[:4]}"
        meta = {
            "category": body.category,
            "subcategory": body.name or body.category,
            "colors": res["colors"],
            "wear_count": 0,
            **({"local_tag": body.local_tag} if body.local_tag else {}),
        }
    w.save_photo(item_id, res["png"], meta)
    steps = [
        {"stage": "input", "method": "data", "name": "Photo", "detail": f"{len(data) // 1024} KB"},
        *({"stage": "code", "method": m, "name": n, "detail": d} for m, n, d in res["steps"]),
        {
            "stage": "output",
            "method": "data",
            "name": "Cutout",
            "detail": f"saved as demo_wardrobe/{item_id}.png",
        },
    ]
    return {"item_id": item_id, "colors": res["colors"], "method": res["method"], "pipeline": steps}


@router.delete("/wardrobe/items/{item_id}", status_code=204)
async def delete_photo(item_id: str):
    if not _ward().delete(item_id):
        raise HTTPException(404, "nothing to delete")


@router.get("/photos/{name}", include_in_schema=False)
async def photo(name: str):
    w = _ward()
    p = w.photos_dir / name
    if not re.fullmatch(r"[A-Za-z0-9_\-]+\.png", name) or not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/png")
