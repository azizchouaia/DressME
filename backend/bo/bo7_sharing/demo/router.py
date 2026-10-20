"""Owner: BO7 · browser demo of M10 + M15 (dev only). Open http://localhost:8000/bo7/demo

Served by the API itself (same origin), so it works without Flutter and without CORS settings.
The wardrobe is M1's (wardrobe digitiser, BO3): this page lists it and adds pieces through M1's API
(`items`, `classify`, `update_item`, `delete_item`). The BO7 demo photos (bo/bo7_sharing/demo_wardrobe/) are
served on /bo7/demo/photos; they are put in M1 for the demo users by bo/bo7_sharing/m01_seed.py.
"""

import base64
import re
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from bo.bo7_sharing import m01_seed
from bo.bo7_sharing.demo import cutout
from modules.m15_challenges.singleton import challenges_agent
from modules.m15_challenges.wardrobe import M1Wardrobe

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


def _m1() -> M1Wardrobe | None:
    w = challenges_agent.wardrobe
    return w if isinstance(w, M1Wardrobe) else None


@router.get("/wardrobe")
async def demo_wardrobe(user_id: str = "usr_042"):
    """The user's wardrobe, read from M1 (or from the fixture wardrobe in the tests)."""
    w = challenges_agent.wardrobe
    out = []
    extra = {r["item_id"]: r for r in (w._added() if hasattr(w, "_added") else [])}
    for g in w.items(user_id):
        main = max(g.colors, key=lambda c: c.share) if g.colors else None
        if _m1():
            url = g.image_raw if g.image_raw and g.image_raw.startswith("/") else None
        else:
            photo = w.photo_path(g.item_id) if hasattr(w, "photo_path") else None
            url = f"/bo7/demo/photos/{g.item_id}.png?v={int(photo.stat().st_mtime)}" if photo else None
        out.append(
            {
                "item_id": g.item_id,
                "name": g.subcategory or g.category.value,
                "category": g.category.value,
                "color_hex": main.hex if main else "#C9C6CC",
                "color": main.name if main else None,
                "local_tag": g.local_tag,
                "photo_url": url,
                "image": g.image_cutout,  # file path, passed back to /m10/cards by the demo page
                "added": g.item_id in extra or bool(_m1()),
                "description": extra.get(g.item_id, {}).get("description"),
                "source": "M1" if _m1() else extra.get(g.item_id, {}).get("source"),
            }
        )
    return out


class PhotoIn(BaseModel):
    image: str = Field(description="data URI of the photo (jpg, png, webp)")
    user_id: str = "usr_042"
    item_id: str | None = Field(None, description="mock wardrobe only: existing item to give a photo to")
    category: Category | None = None
    name: str | None = Field(None, max_length=40)
    local_tag: str | None = Field(None, max_length=40)


async def _add_to_m1(w: M1Wardrobe, body: PhotoIn) -> dict:
    """Photo → M1 classify (add to the wardrobe) → M1 update_item with what the user typed."""
    from modules.m01_wardrobe.contract import ClassifyMode, ClassifyRequest, ItemUpdate, OnDuplicate

    if body.item_id:
        raise HTTPException(400, "M1 keeps the photo of a piece: delete it and add it again")
    impl = w.impl()
    mocked = getattr(impl, "__name__", "").endswith(".mock")
    image, steps = body.image, []
    if mocked:  # M1 mock does not remove backgrounds: the BO7 dev cutout does it so the card looks right
        try:
            res = cutout.run(base64.b64decode(body.image.split(",", 1)[-1]))
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, f"cannot read this image: {e}") from e
        image = "data:image/png;base64," + base64.b64encode(res["png"]).decode()
        steps = [{"stage": "code", "method": m, "name": n, "detail": d} for m, n, d in res["steps"]]
    try:
        out = await impl.classify(
            ClassifyRequest(user_id=body.user_id, image=image, mode=ClassifyMode.add_to_wardrobe,
                            on_duplicate=OnDuplicate.add)
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"M1 could not read this image: {e}") from e
    g = out.garment
    upd = {"category": body.category, "subcategory": body.name, "brand": body.local_tag}
    if mocked and res["colors"]:
        upd["colors"] = res["colors"]
    upd = {k: v for k, v in upd.items() if v}
    if upd:
        g = await impl.update_item(body.user_id, g.item_id, ItemUpdate(**upd))
    if body.local_tag:
        w.local_brands.add(body.local_tag)  # a Tunisian maker typed by the user counts for local challenges
    steps = [
        {"stage": "input", "method": "data", "name": "Photo", "detail": f"{len(body.image) * 3 // 4096} KB"},
        *steps,
        {"stage": "code", "method": "M1", "name": "M1 classify",
         "detail": f"{g.category.value} · {g.subcategory}"},
        {"stage": "output", "method": "data", "name": "Wardrobe item", "detail": f"{g.item_id} saved in M1"},
    ]
    colors = [c.model_dump() for c in g.colors]
    return {"item_id": g.item_id, "colors": colors, "method": "m1", "pipeline": steps}


@router.post("/wardrobe/items")
async def add_photo(body: PhotoIn):
    """Adds a garment to the user's M1 wardrobe (mock wardrobe: saves the cutout in demo_wardrobe/)."""
    m1 = _m1()
    if m1:
        return await _add_to_m1(m1, body)
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
async def delete_photo(item_id: str, user_id: str = "usr_042"):
    m1 = _m1()
    if m1:
        from modules.m01_wardrobe.contract import ItemNotFoundError

        try:
            await m1.impl().delete_item(user_id, item_id)
        except ItemNotFoundError as e:
            raise HTTPException(404, "nothing to delete") from e
        return
    if not _ward().delete(item_id):
        raise HTTPException(404, "nothing to delete")


@router.get("/photos/{name}", include_in_schema=False)
async def photo(name: str):
    w = challenges_agent.wardrobe
    folder = w.photos_dir if getattr(w, "photos_dir", None) else m01_seed.PHOTOS
    p = folder / name
    if not re.fullmatch(r"[A-Za-z0-9_\-]+\.png", name) or not p.exists():
        raise HTTPException(404)
    return FileResponse(p, media_type="image/png")
