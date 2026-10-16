"""M8: parse a request, rank with the person's tastes, explain the outfit, retrieve shops.

Vectors come in on the payload so this module does not download a model.
Set LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL to let a hosted model speak.
The key stays in the environment. It is never written here.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

from .taste import closest, cosine, taste_profile
from .text import parse_request

SLOT_OF = {
    "t-shirt": "top",
    "shirt": "top",
    "top": "top",
    "blouse": "top",
    "jeans": "bottom",
    "pants": "bottom",
    "shorts": "bottom",
    "bottom": "bottom",
    "skirt": "bottom",
    "jacket": "outer",
    "coat": "outer",
    "outer": "outer",
    "shoes": "shoes",
    "sneakers": "shoes",
}
COLD = {"rain", "rainy", "cold", "wind", "windy", "snow", "snowy", "winter"}
_WORDS = re.compile(r"[a-z0-9]+")


def parse(req: dict) -> dict:
    payload = req.get("payload") or {}
    parsed = parse_request(str(payload.get("message") or payload.get("text") or ""))
    for key in ("weather", "season", "occasion", "size"):
        if payload.get(key):
            parsed[key] = payload[key]
    if payload.get("budget") is not None:
        parsed["budget"] = payload["budget"]
    return {"result": parsed, "mocked": False}


def explain(req: dict) -> dict:
    payload = req.get("payload") or {}
    text = _explain(
        payload.get("pieces") or [],
        payload.get("conditions") or {},
        bool(payload.get("tastes")),
        bool(payload.get("from_photo")),
    )
    return {"result": {"text": text}, "mocked": False}


def recommend(req: dict) -> dict:
    payload = req.get("payload") or {}
    user_id = str(req.get("user_id") or "user")
    ranked = rank_pieces(payload.get("pieces") or [], payload, user_id)
    return {"result": {"pieces": ranked["pieces"], "tastes": ranked["taste_names"], "exploration": ranked["exploration"]}, "mocked": False}


def chat(req: dict) -> dict:
    payload = req.get("payload") or {}
    user_id = str(req.get("user_id") or "user")
    parsed = parse(req)["result"]
    ranked = rank_pieces(payload.get("pieces") or [], {**payload, **parsed}, user_id)
    shops = retrieve_shops(" ".join(filter(None, [parsed.get("query"), parsed.get("weather"), parsed.get("occasion")])))
    spoken = _explain(ranked["pieces"], parsed, bool(ranked["taste_names"]), False)
    if shops:
        spoken += " Shops that carry this kind of look: " + "; ".join(f"{shop['name']} in {shop['city']}" for shop in shops) + "."
    spoken = _hosted_voice(spoken, ranked) or spoken
    return {
        "result": {
            "reply": spoken,
            "request": parsed,
            "pieces": ranked["pieces"],
            "tastes": ranked["taste_names"],
            "exploration": ranked["exploration"],
            "shops": shops,
        },
        "mocked": False,
    }


def rank_pieces(raw_pieces: list[dict], conditions: dict, user_id: str) -> dict:
    pieces = [_piece(item) for item in raw_pieces if item.get("vector")]
    vectors = {piece["id"]: piece["vector"] for piece in pieces}
    seed = _seed(user_id)
    profile = taste_profile(list(conditions.get("events") or []), vectors, seed)
    query = conditions.get("query_vector")
    context = conditions.get("context_vector")
    scored = []
    for piece in pieces:
        if not _allowed(piece, conditions):
            continue
        scored.append({**_public(piece), "score": _score(piece, query, context, profile["tastes"]), "source": "match"})
    scored.sort(key=lambda item: item["score"], reverse=True)
    scored = scored[:8]
    exploration = profile["exploration"]
    if exploration is not None:
        pool = [piece for piece in pieces if _allowed(piece, conditions)]
        if pool:
            probe = max(pool, key=lambda piece: cosine(piece["vector"], exploration))
            row = {**_public(probe), "score": round(cosine(probe["vector"], exploration), 4), "source": "explore"}
            if any(item["id"] == probe["id"] for item in scored):
                for item in scored:
                    if item["id"] == probe["id"] and closest(probe["vector"], profile["tastes"]) < cosine(probe["vector"], exploration):
                        item["source"] = "explore"
            elif scored:
                scored[-1] = row
            else:
                scored = [row]
    names = {piece["id"]: piece["name"] for piece in pieces}
    return {
        "pieces": scored,
        "taste_names": [[names.get(piece_id, piece_id) for piece_id in group] for group in profile["members"]],
        "exploration": "nearby" if exploration is not None else "",
    }


def retrieve_shops(query: str, limit: int = 2) -> list[dict]:
    catalog = json.loads(Path(__file__).with_name("shops.json").read_text(encoding="utf-8"))
    needles = set(_WORDS.findall(query.lower()))
    if not needles:
        return []
    ranked = []
    for shop in catalog:
        hay = set(_WORDS.findall(" ".join(shop.get("styles", []) + [shop.get("note", ""), shop.get("name", "")])))
        score = len(needles & hay)
        if score:
            ranked.append((score, shop))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [{"id": shop["id"], "name": shop["name"], "city": shop["city"], "why": shop["note"]} for _, shop in ranked[:limit]]


def _piece(item: dict) -> dict:
    category = str(item.get("category") or "top")
    return {
        "id": str(item.get("id")),
        "name": str(item.get("name") or item.get("id")),
        "category": category,
        "slot": SLOT_OF.get(category.lower(), "other"),
        "vector": [float(value) for value in item["vector"]],
        "size": item.get("size"),
        "price": item.get("price"),
        "stock": int(item.get("stock") if item.get("stock") is not None else 1),
    }


def _allowed(piece: dict, conditions: dict) -> bool:
    if piece["stock"] <= 0:
        return False
    budget = conditions.get("budget")
    if budget is not None and piece["price"] is not None and float(piece["price"]) > float(budget):
        return False
    want = str(conditions.get("size") or "")
    have = piece.get("size")
    if want and have and want[:1].isdigit() == str(have)[:1].isdigit() and want.lower() != str(have).lower():
        return False
    return True


def _score(piece: dict, query, context, tastes: list[list[float]]) -> float:
    parts: list[tuple[float, float]] = []
    if query:
        parts.append((0.55, cosine(query, piece["vector"])))
    if tastes:
        parts.append((0.25, closest(piece["vector"], tastes)))
    if context:
        parts.append((0.20, cosine(context, piece["vector"])))
    if not parts:
        return 0.0
    weight = sum(item[0] for item in parts)
    return round(sum(item[0] * item[1] for item in parts) / weight, 4)


def _public(piece: dict) -> dict:
    return {"id": piece["id"], "name": piece["name"], "slot": piece["slot"]}


def _explain(pieces: list[dict], conditions: dict, has_taste: bool, from_photo: bool) -> str:
    if not pieces:
        return "Nothing in the wardrobe passes the size, budget, and stock filters."
    names = ", ".join(item.get("name", "") for item in pieces)
    bits = []
    if from_photo:
        bits.append("the photo")
    if has_taste:
        bits.append("the tastes already saved for this person")
    situation = " ".join(str(conditions.get(key) or "") for key in ("weather", "season", "occasion")).strip()
    if situation:
        bits.append(situation)
    why = f" because of {' and '.join(bits)}" if bits else ""
    taste_line = (
        " Likes are kept as separate tastes, and one suggestion stays close to them to see if the person moves that way."
        if has_taste
        else " There is no saved taste yet."
    )
    return f"{names}{why}.{taste_line}"


def _seed(user_id: str) -> int:
    raw = os.environ.get(f"DRESSME_EXPLORE_SEED_{user_id}")
    if raw and raw.isdigit():
        return int(raw)
    return 1 + sum(ord(ch) for ch in user_id) % 997


def _hosted_voice(facts: str, ranked: dict) -> str | None:
    base = os.environ.get("LLM_BASE_URL", "").rstrip("/")
    key = os.environ.get("LLM_API_KEY", "")
    model = os.environ.get("LLM_MODEL", "")
    if not base or not key or not model:
        return None
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are the DressMe stylist. Repeat only the pieces and reasons you are given. Do not invent prices.",
                },
                {"role": "user", "content": facts + " Tastes: " + json.dumps(ranked["taste_names"])},
            ],
        }
    ).encode()
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "Dressme-stylist/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode())
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None
    choices = payload.get("choices") or []
    if not choices:
        return None
    return (choices[0].get("message") or {}).get("content") or None
