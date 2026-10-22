"""Calls to the other modules. Rule: call their API (or mock), never re-implement them.

`config.yaml -> real: [...]` lists the modules called for real; the others answer with the mock data below.
A real call that fails also falls back to the mock, so M14 always answers. Every call returns
(value, "real" | "mock") so the answers can say where each fact comes from (`sources`).

M7 (same BO) is called in-process; the others over HTTP on `api_url`, with their own contracts:
M1 POST /m01/items · M3 POST /m03/stats · M5 POST /m05/profile, /m05/feedback, /m05/gaps ·
M2 POST /m02/score · M6 POST /m06/verdict · M10 POST /m10/cards.
"""

import asyncio
import logging
from collections.abc import Callable

import httpx

from .paths import CONFIG

log = logging.getLogger("m14.clients")


def _real(module: str) -> bool:
    return module in (CONFIG.get("real") or [])


async def _try(module: str, real_fn: Callable, mock_fn: Callable):
    if _real(module):
        try:
            value = real_fn()
            if asyncio.iscoroutine(value):
                value = await value
            return value, "real"
        except Exception as exc:  # module missing, not merged yet or failing: M14 must still answer
            log.info("%s unavailable (%s): mock", module, exc)
    return mock_fn(), "mock"


def _post(path: str, body: dict) -> dict:
    r = httpx.post(CONFIG["api_url"].rstrip("/") + path, json=body, timeout=CONFIG["timeout_s"])
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- mock data of the other modules
# A small fixed wardrobe so the brief, the looks and the in-store verdict have something to show.
_WARDROBE = [
    ("itm_jean01", "bottom", "jeans", "blue", 18, 89.0),
    ("itm_chem01", "top", "shirt", "white", 11, 65.0),
    ("itm_pull01", "top", "sweater", "beige", 7, 75.0),
    ("itm_bask01", "shoes", "sneakers", "white", 22, 120.0),
    ("itm_robe01", "dress", "dress", "red", 0, 140.0),
    ("itm_vest01", "outerwear", "jacket", "navy", 4, 189.0),
    ("itm_sac01", "accessory", "bag", "black", 9, 95.0),
    ("itm_tsh01", "top", "tshirt", "black", 14, 25.0),
]


_HEX = {
    "blue": "#1F4E9A",
    "white": "#FFFFFF",
    "beige": "#D8C3A5",
    "red": "#C0392B",
    "navy": "#1B2A49",
    "black": "#111111",
}


def mock_items(user_id: str) -> list[dict]:
    """Same shape as M1's WardrobeItem (shared Garment), so M2 / M10 accept it when they are real."""
    return [
        {
            "item_id": i,
            "user_id": user_id,
            "image_raw": "",
            "category": c,
            "subcategory": s,
            "colors": [{"name": col, "hex": _HEX[col], "share": 1.0}],
            "wear_count": n,
            "price_tnd": p,
        }
        for i, c, s, col, n, p in _WARDROBE
    ]


def product_as_garment(user_id: str, p: dict) -> dict:
    """An M7 product in the shared Garment shape, to score / draw it next to the client's own pieces."""
    color = p.get("color") or None
    return {
        "item_id": p["product_id"],
        "user_id": user_id,
        "image_raw": p.get("image_url") or "",
        "category": p["category"],
        "subcategory": p.get("subcategory"),
        "colors": [{"name": color, "hex": p.get("color_hex") or "#999999", "share": 1.0}] if color else [],
        "local_tag": p.get("shop_name"),
        "price_tnd": p.get("price_tnd"),
    }


def mock_profile(user_id: str) -> dict:
    return {
        "archetype": "casual",
        "likes": ["linen", "denim"],
        "dislikes": ["prints"],
        "colours": ["beige", "white", "navy"],
        "style_vector": None,
    }


# ---------------------------------------------------------------- M1 / M3 / M5 (client data)
async def wardrobe(user_id: str):
    return await _try(
        "m1", lambda: _post("/m01/items", {"user_id": user_id})["items"], lambda: mock_items(user_id)
    )


async def wear_stats(user_id: str, item_ids: list[str]):
    def real():
        result = _post("/m03/stats", {"user_id": user_id, "payload": {"item_ids": item_ids}})["result"]
        return {i["item_id"]: i.get("wear_count", 0) for i in result.get("items", [])}

    def mock():
        return {i: n for i, _, _, _, n, _ in _WARDROBE if i in item_ids}

    return await _try("m3", real, mock)


async def style_profile(user_id: str):
    def real():
        result = _post("/m05/profile", {"user_id": user_id, "payload": {}})["result"]
        if not result.get("archetype") and not result.get("likes"):
            raise ValueError("M5 profile has no style fields yet")
        return result

    return await _try("m5", real, lambda: mock_profile(user_id))


async def style_gaps(user_id: str):
    def real():
        result = _post("/m05/gaps", {"user_id": user_id, "payload": {}})["result"]
        gaps = result.get("gaps")
        if not isinstance(gaps, list):
            raise ValueError("M5 gaps not available yet")
        return [g if isinstance(g, str) else g.get("label", str(g)) for g in gaps]

    return await _try("m5", real, lambda: ["dress shoes"])


async def send_corrections(user_id: str, pro_id: str, corrections: dict):
    """F3: the stylist's corrections are human labels for M5 (feedback API)."""
    body = {
        "user_id": user_id,
        "payload": {"source": "stylist", "pro_id": pro_id, "corrections": corrections},
    }
    return await _try("m5", lambda: _post("/m05/feedback", body) and True, lambda: True)


# ---------------------------------------------------------------- M2 / M6 / M10 (decisions, cards)
async def look_score(user_id: str, pieces: list[dict]):
    """M2 compatibility of the look. `pieces` = the client's M1 items + M7 products, all Garment-shaped:
    they are sent inline (`payload.items`) because M2 only scores pieces it is given (shop pieces are not
    in the client's wardrobe). M2 needs at least 2 pieces; otherwise the mock answers."""

    def real():
        payload = {"items": pieces, "outfits": [[p["item_id"] for p in pieces]]}
        out = _post("/m02/score", {"user_id": user_id, "payload": payload})
        outfits = (out.get("result") or {}).get("outfits") or out.get("outfits") or []
        return float(outfits[0]["score"])

    return await _try("m2", real, lambda: round(min(0.95, 0.6 + 0.05 * len(pieces)), 2))


async def verdict(user_id: str, product: dict, language: str):
    """F5: M6 Smart Buy on the CLIENT's wardrobe for a piece of the shop."""
    body = {
        "user_id": user_id,
        "probe_image": product.get("image_url"),
        "price_tnd": product.get("price_tnd"),
        "shop_brand": product.get("shop"),
        "language": language,
        "session_id": "m14_instore",
    }

    def mock():
        return {
            "verdict": "think",
            "score": 55,
            "reasons": ["Smart Buy (M6) not connected yet: default opinion"],
            "explanation": "To be confirmed with Smart Buy when it is available.",
        }

    return await _try("m6", lambda: _post("/m06/verdict", body), mock)


async def share_card(user_id: str, pieces: list[dict], message: str | None, language: str):
    """M10 card of the look; `pieces` are Garment-shaped (M10 CardItem needs item_id + category)."""

    def label(p: dict) -> str:
        colour = (p.get("colors") or [{}])[0].get("name")
        return " ".join(x for x in (p.get("subcategory") or p["category"], colour) if x)

    body = {
        "user_id": user_id,
        "kind": "outfit",
        "caption": message,
        "language": "fr" if language == "ar" else language,  # M10 captions: en / fr / tn
        "items": [
            {
                "item_id": p["item_id"],
                "category": p["category"],
                "label": label(p),
                "image": p.get("image_cutout") or p.get("image_raw") or None,
                "color_hex": (p.get("colors") or [{}])[0].get("hex"),
                "brand": p.get("local_tag"),
            }
            for p in pieces
        ][:8],
    }

    def real():
        out = _post("/m10/cards", body)
        return {"card_url": out["image_url"], "share_url": out["share_url"]}

    return await _try("m10", real, lambda: {"card_url": None, "share_url": None})


# ---------------------------------------------------------------- M7 (same BO, in-process)
async def product(product_id: str):
    from modules.m07_local_catalogue import service as m7

    return await _try("m7", lambda: m7.product(product_id), lambda: None)


async def shop_exists(shop: str):
    from modules.m07_local_catalogue import service as m7

    async def real():
        return any(s["shop"] == shop for s in await m7.shops())

    return await _try("m7", real, lambda: True)


async def recent_searches(user_id: str, n: int = 5):
    """What the client searched with localshop (BO6's own memory)."""
    from modules.m07_local_catalogue import service as m7

    def real():
        return [h["request"] for h in m7.memory().history(user_id, n) if h.get("request")]

    return await _try("m7", real, lambda: [])
