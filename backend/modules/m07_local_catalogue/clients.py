"""Calls to other shared modules. Rule: call their API (or mock), never re-implement them.

`config.yaml -> real: [...]` lists the modules called for real (once their branch is merged); the others
answer with a simulation below, and every answer says which one was used (`sources`). A real call that
fails also falls back to the simulation, so localshop always answers.

M1 POST /m01/items (the user's wardrobe) · M2 POST /m02/score and /m02/complete (compatibility and outfits,
OutfitTransformer) · M5 style vector (in-process, through M5's mock or service) · M9 BO9's 3D service
POST <tryon.url>/reconstruct (photo -> GLB) · M14 loyalty codes of the boutique accounts (same BO).
"""

import logging
from collections.abc import Callable

import httpx

from .paths import CONFIG

log = logging.getLogger("m07.clients")


def style_vector_from_m5(user_id: str | None, vector_id: str) -> list[float] | None:
    """Resolve a style vector id ("vec_u042", as in the architecture doc) through M5 Style profile.

    Uses M5's mock or service the same way M5's router does. Returns None while M5 does not expose
    the vector yet; the caller then ranks without the style part and says so.
    """
    try:
        from modules.m05_style_profile import mock, service
        from shared.config import settings

        impl = mock if getattr(settings, "use_mocks", True) else service
        answer = impl.profile({"user_id": user_id, "payload": {"style_vector_id": vector_id}})
    except Exception as exc:  # M5 missing, not implemented yet, or failing: M7 must still answer
        log.warning("M5 style vector %s unavailable: %s", vector_id, exc)
        return None
    vector = (answer.get("result") or {}).get("style_vector")
    if isinstance(vector, list) and vector and all(isinstance(v, int | float) for v in vector):
        return [float(v) for v in vector]
    return None


# ---------------------------------------------------------------- real call, or the simulation
def is_real(module: str) -> bool:
    """The module is listed in config.yaml `real` (called over HTTP; the simulation answers otherwise)."""
    return module in (CONFIG.get("real") or [])


def _try(module: str, real_fn: Callable, mock_fn: Callable):
    """(value, "real" | "mock"): the module's answer when it is listed in `real` and answers, else mock."""
    if is_real(module):
        try:
            return real_fn(), "real"
        except Exception as exc:  # module missing, not merged yet or failing: localshop must still answer
            log.info("%s unavailable (%s): simulation", module, exc)
    return mock_fn(), "mock"


def _post(path: str, body: dict) -> dict:
    r = httpx.post(CONFIG["api_url"].rstrip("/") + path, json=body, timeout=CONFIG["timeout_s"])
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------- M1: the user's wardrobe
# Simulated wardrobe (same pieces as M14's), in the shared Garment shape, until M1 is merged.
_WARDROBE = [
    ("itm_jean01", "bottom", "jeans", "blue"),
    ("itm_chem01", "top", "shirt", "white"),
    ("itm_pull01", "top", "sweater", "beige"),
    ("itm_bask01", "shoes", "sneakers", "white"),
    ("itm_robe01", "dress", "dress", "red"),
    ("itm_vest01", "outerwear", "jacket", "navy"),
    ("itm_sac01", "accessory", "bag", "black"),
    ("itm_tsh01", "top", "tshirt", "black"),
    ("itm_pant01", "bottom", "trousers", "black"),
    ("itm_jupe01", "bottom", "skirt", "beige"),
    ("itm_escar01", "shoes", "heels", "black"),
    ("itm_mant01", "outerwear", "coat", "camel"),
]


def mock_wardrobe(user_id: str) -> list[dict]:
    return [
        {
            "item_id": i,
            "user_id": user_id,
            "image_raw": "",
            "category": c,
            "subcategory": s,
            "colors": [{"name": col}],
        }
        for i, c, s, col in _WARDROBE
    ]


def wardrobe(user_id: str) -> tuple[list[dict], str]:
    return _try(
        "m1", lambda: _post("/m01/items", {"user_id": user_id})["items"], lambda: mock_wardrobe(user_id)
    )


# ---------------------------------------------------------------- M2: compatibility and outfits
# Simulation of M2, used until it is merged: which slots complete a piece, and a colour rule.
_COMPLETES = {
    "top": ["bottom", "shoes", "outerwear", "accessory"],
    "bottom": ["top", "shoes", "outerwear", "accessory"],
    "dress": ["shoes", "outerwear", "accessory"],
    "outerwear": ["top", "bottom", "dress", "shoes"],
    "shoes": ["top", "bottom", "dress", "outerwear"],
    "accessory": ["top", "bottom", "dress", "outerwear"],
    "traditional": ["shoes", "accessory"],
}
# Slots an outfit needs around the piece, in order (the first one varies between the outfits).
_OUTFIT_SLOTS = {
    "top": ["bottom", "shoes"],
    "bottom": ["top", "shoes"],
    "dress": ["shoes", "outerwear"],
    "outerwear": ["top", "bottom", "shoes"],
    "shoes": ["bottom", "top"],
    "accessory": ["top", "bottom", "shoes"],
    "traditional": ["shoes", "accessory"],
}
_NEUTRALS = {"black", "white", "beige", "grey", "navy", "camel", "brown", "gold", ""}


def _colour(g: dict) -> str:
    return ((g.get("colors") or [{}])[0].get("name") or "").lower()


def _pair_score(a: dict, b: dict) -> float:
    """Simulated compatibility: complementary slots, then colours (neutral 0.8, same 0.7, two colours 0.4)."""
    if b["category"] not in _COMPLETES.get(a["category"], []):
        return 0.0
    ca, cb = _colour(a), _colour(b)
    return 0.8 if ca in _NEUTRALS or cb in _NEUTRALS else 0.7 if ca == cb else 0.4


def pair_scores(user_id: str, piece: dict, pieces: list[dict]) -> tuple[dict[str, float], str]:
    """Compatibility (0..1) of a shop piece with each wardrobe piece: M2 /score on the pairs, sent inline."""

    def real():
        payload = {"items": [piece, *pieces], "outfits": [[piece["item_id"], p["item_id"]] for p in pieces]}
        outfits = _post("/m02/score", {"user_id": user_id, "payload": payload})["result"]["outfits"]
        return {next(i for i in o["items"] if i != piece["item_id"]): float(o["score"]) for o in outfits}

    return _try("m2", real, lambda: {p["item_id"]: _pair_score(piece, p) for p in pieces})


def complete(user_id: str, piece: dict, pieces: list[dict], occasion: str, n: int) -> tuple[list[dict], str]:
    """Outfits from the wardrobe around the shop piece: M2 /complete with the piece pinned.
    Each outfit: {item_ids, score, reasons}."""

    def real():
        payload = {
            "items": [piece, *pieces],
            "pinned_item_ids": [piece["item_id"]],
            "context": {"occasion": occasion},
            "options": {"n": n},
        }
        result = _post("/m02/complete", {"user_id": user_id, "payload": payload})["result"]
        return [
            {"item_ids": o["items"], "score": float(o.get("score") or 0), "reasons": o.get("reasons") or []}
            for o in result["outfits"]
        ]

    def mock():
        outfits = []
        for k in range(n):
            ids, scores = [piece["item_id"]], []
            for s, slot in enumerate(_OUTFIT_SLOTS.get(piece["category"], [])):
                options = sorted(
                    (p for p in pieces if p["category"] == slot and p["item_id"] not in ids),
                    key=lambda p: -_pair_score(piece, p),
                )
                pick = (
                    options[min(k, len(options) - 1)]
                    if s == 0 and options
                    else options[0]
                    if options
                    else None
                )
                if pick is not None:
                    ids.append(pick["item_id"])
                    scores.append(_pair_score(piece, pick))
            if len(ids) > 1 and ids not in [o["item_ids"] for o in outfits]:
                outfits.append({"item_ids": ids, "score": round(sum(scores) / len(scores), 2), "reasons": []})
        return outfits

    return _try("m2", real, mock)


def outfit_scores(user_id: str, outfit: list[dict], candidates: list[dict]) -> tuple[dict[str, float], str]:
    """Compatibility (0..1) of the outfit + each shop candidate: M2 /score, every piece sent inline."""
    ids = [g["item_id"] for g in outfit]

    def real():
        payload = {"items": [*outfit, *candidates], "outfits": [[*ids, c["item_id"]] for c in candidates]}
        outfits = _post("/m02/score", {"user_id": user_id, "payload": payload})["result"]["outfits"]
        return {next(i for i in o["items"] if i not in ids): float(o["score"]) for o in outfits}

    def mock():
        return {
            c["item_id"]: round(sum(_pair_score(c, g) for g in outfit) / len(outfit), 2) for c in candidates
        }

    return _try("m2", real, mock)


# ---------------------------------------------------------------- M9 (BO9): photo -> 3D model
def reconstruct(image: bytes) -> tuple[bytes | None, str]:
    """GLB of the piece from its photo (BO9's TripoSR service); None while it is simulated."""
    cfg = CONFIG["tryon"]

    def real():
        r = httpx.post(
            cfg["url"].rstrip("/") + "/reconstruct",
            content=image,
            headers={"Content-Type": "image/jpeg", "X-TripoSR-Resolution": str(cfg["resolution"])},
            timeout=cfg["timeout_s"],
        )
        r.raise_for_status()
        return r.content

    return _try("m9", real, lambda: None)


# ---------------------------------------------------------------- M14 (same BO): loyalty codes of shops
def loyalty_by_shop() -> dict[str, dict]:
    """shop -> its valid loyalty code, set by the shop in its boutique account (M14). Empty if none."""
    try:
        from modules.m14_stylist_mode import service as m14

        return {c["shop"]: c for c in m14.loyalty_codes()}
    except Exception as exc:  # M14 data missing or unreadable: the search still answers
        log.info("loyalty codes unavailable: %s", exc)
        return {}
