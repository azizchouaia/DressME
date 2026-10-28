"""The user's wardrobe as agents see it: catalog (their 3D pieces from M9, else an M2 demo wardrobe),
retrieval of the pieces relevant to a request (RAG, FashionCLIP text space), piece names -> ids, and argument
cleaners for values coming from an LLM."""

from __future__ import annotations

import datetime as dt
import re
from functools import lru_cache

import numpy as np

from shared.agent_bus import ask

ME = "wardrobe"
OCCASIONS = ("work", "casual", "event")
MOODS = ("comfy", "bold", "classy")


# ---------------- the user's wardrobe (catalog) ----------------
async def catalog(user: str) -> dict:
    """{"source", "items": [{id, name, category}], "m2_items": items to pass to M2 or None (demo
    wardrobe)}. Order: the user's M1 wardrobe (BO4 photos), their 3D wardrobe (M9), a demo wardrobe."""
    from shared.user_wardrobe import m1_garments

    mine = m1_garments(user)
    if mine:
        return {"source": "my wardrobe (M1)", "m2_items": mine,
                "items": [{"id": g["item_id"], "name": g["name"], "category": g["category"]} for g in mine]}
    r = await ask("m09_avatar_3d", "items", user_id=user, sender=ME)
    items = (r.get("result") or {}).get("items") or []
    if len(items) >= 2:
        names = {}
        p = await ask("m09_avatar_3d", "pieces", user_id=user, sender=ME)
        for pc in (p.get("result") or {}).get("pieces", []):
            names[pc["piece_id"]] = pc["sheet"].get("name")
        out = []
        for it in items:
            colour = (it.get("colors") or [{}])[0].get("name", "")
            desc = f"{colour} {it.get('subcategory') or it['category']}".strip()
            nm = names.get(it["item_id"])
            same = nm and (nm.lower() in desc.lower() or desc.lower() in nm.lower())
            label = desc if not nm or same else f"{desc} '{nm}'"  # "light grey t-shirt 'elephant'"
            out.append({"id": it["item_id"], "name": label, "category": it["category"]})
        return {"source": "my 3D wardrobe", "items": out, "m2_items": items}
    from modules.m02_recommendation import service as m2  # demo wardrobes of M2 (users demo_f / demo_m)

    who = user if user.startswith("demo_") else "demo_f"
    m2_items = demo_items_with_vectors(who)
    ids = {i["item_id"] for i in m2_items}
    demo = m2.demo_wardrobe(who)
    out = [
        {"id": i["item_id"], "name": i["name"], "category": i["category"]}
        for i in demo["items"]
        if i["item_id"] in ids
    ]
    return {"source": f"demo wardrobe ({who})", "items": out, "m2_items": m2_items}


def demo_items_with_vectors(user: str) -> list[dict]:
    """The M2 demo wardrobe in M1 Garment format with its FashionCLIP vectors (to pass to M2 / M17)."""
    from modules.m02_recommendation.engine import wardrobe as w

    meta, emb, row, demo = w._demo_catalogue()
    out = []
    for iid in demo.get(user, demo.get("demo_f")):
        m = meta[iid]
        out.append(
            {
                "item_id": iid,
                "user_id": user,
                "image_raw": m.get("image") or "",
                "category": m["category"],
                "subcategory": m.get("subcategory"),
                "colors": m.get("colors", []),
                "pattern": m.get("pattern"),
                "embedding": [float(x) for x in emb[row[iid]]],
            }
        )
    return out


@lru_cache(maxsize=512)
def _text_vec(text: str) -> tuple:
    from modules.m02_recommendation.engine import encoder

    return tuple(encoder.embed_texts([text])[0].tolist())


def retrieve(query: str, items: list[dict], k: int = 6) -> list[dict]:
    """RAG step: the pieces of the wardrobe closest to the request (FashionCLIP text space, the encoder M2
    uses), plus every piece named explicitly in the request."""
    if not items:
        return []
    q = np.array(_text_vec(query[:200]))
    sims = [(float(np.dot(q, np.array(_text_vec(it["name"])))), it) for it in items]
    sims.sort(key=lambda s: -s[0])
    low = query.lower()
    named = [it for it in items if any(w in low for w in re.findall(r"[a-z]{4,}", it["name"].lower()))]
    seen, out = set(), []
    for it in named + [s[1] for s in sims[:k]]:
        if it["id"] not in seen:
            seen.add(it["id"])
            out.append(it)
    return out[: k + 3]


def resolve_pieces(refs, items: list[dict]) -> list[dict]:
    """Piece references from the LLM (ids or names) -> catalog items."""
    if isinstance(refs, str):
        refs = [r for r in re.split(r",| and | et ", refs) if r.strip()]
    out = []
    for ref in refs or []:
        ref = str(ref).strip().lower()
        hit = next((it for it in items if it["id"].lower() == ref), None)
        if hit is None:
            words = set(re.findall(r"[a-z]{3,}", ref))
            best = max(
                items,
                key=lambda it: len(words & set(re.findall(r"[a-z]{3,}", it["name"].lower()))),
                default=None,
            )
            if best and words & set(re.findall(r"[a-z]{3,}", best["name"].lower())):
                hit = best
        if hit and hit not in out:
            out.append(hit)
    return out


def day_of(value) -> dt.date:
    v = str(value or "today").lower()
    today = dt.date.today()
    if "tomorrow" in v or "demain" in v:
        return today + dt.timedelta(days=1)
    try:
        return dt.date.fromisoformat(v[:10])
    except ValueError:
        return today


def pick(value, allowed, default):
    v = str(value or "").lower()
    return next((a for a in allowed if a in v), default)


# ---------------- tools ----------------
