"""The signed-in user's REAL wardrobe (M1, BO4) in the format the outfit models need (M2 / BO1 / BO2).

M1 keeps, for every piece, its FashionCLIP image embedding (512). The pretrained OutfitTransformer of M2
takes [FashionCLIP image 512 | FashionCLIP text 512 of the piece's description]. Both modules use the same
model (patrickjohncyh/fashion-clip), so the item vector is: M1 image embedding + M2's text embedding of
"navy linen shirt". No dataset needed: the user's own pieces replace the Kaggle demo wardrobe.

Returns [] (callers fall back to the 3D wardrobe or the demo wardrobe) when: demo user, M1 on its mock,
database down, or fewer than 2 pieces.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

MIN_PIECES = 2


def _run(coro):
    """Run an async M1 call from sync code, also inside the API's event loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def description(g: dict) -> str:
    colour = ((g.get("colors") or [{}])[0] or {}).get("name") or ""
    parts = [colour, g.get("pattern") if g.get("pattern") not in (None, "solid") else "", g.get("material") or "",
             g.get("subcategory") or g.get("category") or "piece"]
    return " ".join(p for p in parts if p).strip()


@lru_cache(maxsize=2048)
def _text_vec(text: str) -> tuple:
    from modules.m02_recommendation.engine import encoder

    return tuple(encoder.embed_texts([text])[0].tolist())


async def _fetch(user_id: str) -> tuple[list[dict], dict[str, list[float]]]:
    from modules.m01_wardrobe import service, store
    from modules.m01_wardrobe.contract import ItemsRequest

    res = await service.items(ItemsRequest(user_id=user_id))
    items = [it.model_dump(mode="json") for it in res.items]
    vectors = await store.get_embeddings(user_id, [it["item_id"] for it in items]) if items else {}
    return items, vectors


def m1_garments(user_id: str | None) -> list[dict]:
    """The user's active M1 pieces as Garment dicts + 'embedding' (1024) + 'name'. [] when not usable."""
    if not user_id or user_id.startswith("demo_") or user_id == "me":
        return []
    try:
        from modules.m01_wardrobe.config import use_mocks
        from shared.config import settings

        if use_mocks(settings.use_mocks):
            return []  # M1 mock = shared demo pieces, not this user's wardrobe
        items, vectors = _run(_fetch(user_id))
    except Exception:  # noqa: BLE001 - M1 / database unavailable: callers use another wardrobe
        return []
    out = []
    for g in items:
        img = vectors.get(g["item_id"])
        if not img or len(img) != 512:
            continue
        desc = description(g)
        try:
            text = list(_text_vec(desc))
        except Exception:  # noqa: BLE001 - FashionCLIP text encoder not installed
            return []
        out.append({**g, "user_id": g.get("user_id") or user_id, "status": "available", "embedding": [float(x) for x in img] + text, "name": desc})
    return out if len(out) >= MIN_PIECES else []
