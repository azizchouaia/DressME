"""Owner: BO7 · Tunisian shops and brands, read from M7 (local catalogue, BO6) through its public functions.

Used by the BO7 task "shared looks tagged with local brands" (M7 + M10):
  - `shops()`: the 43 Tunisian shops / brands of M7 (name, city, website, kind), to tag a piece or a look;
  - `shop_the_look(pieces)`: for each piece of a shared look, the closest products sold by Tunisian shops
    (M7 search with the piece's colour and type), shown under the card as "Shop this look in Tunisia";
  - `names()`: shop names, so a piece whose brand is an M7 shop counts as a Tunisian maker in M15.
Nothing in modules/m07_local_catalogue is changed (rule 4: only call the owner's API).
"""

import re

_SHOPS: list[dict] | None = None
CATEGORIES = {"top", "bottom", "dress", "outerwear", "shoes", "accessory", "traditional"}

TYPE_WORDS = {  # M1 / BO7 piece names → words M7 understands (French catalogue, FR/EN parser)
    "t-shirt": "t-shirt", "shirt": "chemise", "blouse": "blouse", "polo": "polo", "hoodie": "sweat",
    "top": "top", "shorts": "short", "trousers": "pantalon", "jeans": "jean", "skirt": "jupe",
    "dress": "robe", "jacket": "veste", "blazer": "blazer", "coat": "manteau", "shoes": "chaussures",
    "sneakers": "baskets", "hat": "chapeau", "cap": "casquette", "bag": "sac", "jebba": "jebba",
    "blouza": "blouza", "kachabia": "kachabia", "sefsari": "sefsari", "chechia": "chechia",
    "balgha": "balgha",
}  # fmt: skip
COLOR_WORDS = {
    "black": "noir", "white": "blanc", "grey": "gris", "beige": "beige", "brown": "marron", "red": "rouge",
    "pink": "rose", "orange": "orange", "yellow": "jaune", "green": "vert", "blue": "bleu",
    "navy": "bleu marine",
    "purple": "violet",
}  # fmt: skip


def _same_kind(query: str, row: dict) -> bool:
    """The product's name mentions the piece type, or the type is generic (chaussures, top...)."""
    kind = query.split()[0] if query else ""
    generic = {"chaussures", "top", "sac", "chapeau"}
    name = (row.get("item") or "").lower()
    return kind in generic or kind[:5] in name or (row.get("subcategory") or "") in query


def _kind(row: dict) -> str:
    return "Tunisian brand" if row.get("origin_type") == "local_brand" else "Tunisian shop"


async def _call(fn, *args):
    """M7 loads its catalogue on the first call; without torch that first call stops after loading it
    (FashionCLIP missing) and the next calls work with keyword search. One retry covers it."""
    try:
        return await fn(*args)
    except ModuleNotFoundError:
        return await fn(*args)


async def shops() -> list[dict]:
    global _SHOPS
    if _SHOPS is None:
        from modules.m07_local_catalogue import service

        try:
            rows = await _call(service.shops)
        except Exception:  # noqa: BLE001 — M7 unavailable: BO7 keeps working without shop tags
            return []
        _SHOPS = [
            {
                "shop": r["shop"],
                "city": r.get("city"),
                "url": r.get("shop_url"),
                "kind": _kind(r),
                "products": r.get("products", 0),
            }
            for r in rows
        ]
    return _SHOPS


async def names() -> set[str]:
    return {s["shop"] for s in await shops()}


def shop_id(name: str) -> str:
    """Stable id of an M7 shop, stored in M1 `store_id` when a piece was bought there."""
    return "m07:" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def query_for(name: str, color: str | None) -> str:
    words = name.lower()
    kind = next((fr for en, fr in TYPE_WORDS.items() if en in words), words.split()[-1] if words else "")
    return f"{kind} {COLOR_WORDS.get((color or '').lower(), '')}".strip()


async def shop_the_look(pieces: list[dict], per_piece: int = 2) -> list[dict]:
    """pieces: [{item_id, name, color, category}] → [{item_id, query, products: [...]}]."""
    from modules.m07_local_catalogue import service

    out = []
    for p in pieces:
        q = query_for(p.get("name") or p.get("category") or "", p.get("color"))
        try:
            cat = p.get("category") if p.get("category") in CATEGORIES else None
            req = {"query": q, "k": per_piece * 4, **({"category": cat} if cat else {})}
            res = await _call(service.search, req)
            if cat:  # keep products of the same type (no watch for a t-shirt, no shoe bag for shoes)
                same = [
                    r
                    for r in res.get("results", [])
                    if r.get("category") == cat and (cat == "traditional" or _same_kind(q, r))
                ]
                res["results"] = same
        except Exception:  # noqa: BLE001
            res = {"results": []}
        out.append(
            {
                "item_id": p.get("item_id"),
                "query": q,
                "note": res.get("note"),
                "products": [
                    {
                        "shop": r["shop"],
                        "item": r["item"],
                        "price_tnd": r.get("price_tnd"),
                        "photo": f"/m07/{r['image_path']}" if r.get("image_path") else r.get("image_url"),
                        "url": r.get("product_url") or r.get("shop_url"),
                        "kind": _kind(r),
                    }
                    for r in res.get("results", [])[:per_piece]
                ],
            }
        )
    return out
