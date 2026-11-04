"""What is missing in the user's REAL wardrobe (M1): a capsule of versatile essentials, checked piece by piece.

One answer for every place that talks about gaps:
- BO5 Smart Buy: "fills a gap" in the verdict, and the shopping list (Smart Buy gap format "white|black t-shirt");
- BO1 "What I'm missing" (gap_filling idea agent);
- M5 /m05/gaps (no fake data any more).

A gap is an essential that the wardrobe does not have in one of its usual colours. Ordered by how many outfits
it unlocks (tops and bottoms first). No dataset, no mock: only the user's own pieces.
"""

from __future__ import annotations

import re

# M1 subcategory -> Smart Buy type (modules/m06_smartbuy/synthetic.TYPES)
_TYPE = [
    (r"t-?shirt|tee|tank", "t-shirt"), (r"polo|blouse", "shirt"), (r"shirt|chemise", "shirt"),
    (r"sweat|hoodie|pull|jumper|cardigan|knit", "sweater"), (r"jean|denim pant", "jeans"), (r"chino", "chinos"),
    (r"trouser|pant|pantalon", "trousers"), (r"skirt|jupe", "skirt"), (r"sneaker|basket|trainer", "sneakers"),
    (r"loafer|mocassin|dress shoe|oxford|derby", "loafers"), (r"boot|botte", "boots"), (r"sandal", "sandals"),
    (r"blazer|suit|costume", "blazer"), (r"coat|manteau|trench|parka", "coat"), (r"jacket|veste|blouson", "jacket"),
    (r"jebba|kaftan|jebbah", "jebba"), (r"dress|robe", "dress"),
]

# (gap in Smart Buy format, why it matters, gender: None = everyone)
ESSENTIALS = [
    ("white|black t-shirt", "a plain tee goes with every bottom you own", None),
    ("blue|black jeans", "dark jeans pair with almost every top", None),
    ("white|blue|navy shirt", "a light shirt makes work and event outfits", None),
    ("white sneakers", "white sneakers match casual and smart-casual looks", None),
    ("beige|navy|grey chinos", "neutral chinos dress up a t-shirt or a shirt", None),
    ("navy|black|grey blazer", "a dark blazer turns any outfit into a work look", None),
    ("grey|navy|black sweater", "a neutral sweater layers over shirts and tees", None),
    ("black|brown loafers", "smart shoes for work and events", None),
    ("black|navy|beige jacket", "a light jacket for spring and autumn evenings", None),
    ("black|beige coat", "a warm coat for winter", None),
    ("black|navy dress", "a dark dress covers events and dinners", "female"),
]

_COLOUR_ALIASES = {"charcoal": "grey", "denim": "blue", "cream": "white", "ecru": "beige", "khaki": "beige",
                   "camel": "beige", "tan": "beige", "light blue": "blue", "dark blue": "navy"}


def type_of(item: dict) -> str | None:
    text = f"{item.get('subcategory') or ''} {item.get('category') or ''}".lower()
    return next((t for rx, t in _TYPE if re.search(rx, text)), None)


def colour_of(item: dict) -> str:
    cols = item.get("colors") or []
    name = ((cols[0] if cols else {}) or {}).get("name") or ""
    name = name.lower()
    return _COLOUR_ALIASES.get(name, name)


def gaps_for(items: list[dict], gender: str | None = None, k: int = 5) -> list[dict]:
    """[{gap, piece, why, have}] for the essentials the wardrobe misses (have = same type in other colours)."""
    owned = [(type_of(it), colour_of(it)) for it in items]
    out = []
    for gap, why, only in ESSENTIALS:
        if only and gender and gender != only:
            continue
        colours, typ = gap.split(" ", 1)[0].split("|"), gap.split(" ", 1)[1]
        same_type = [c for t, c in owned if t == typ]
        if any(c in colours for c in same_type):
            continue
        piece = f"{colours[0]} {typ}"
        out.append({"gap": gap, "piece": piece, "why": why, "have": len(same_type)})
    return out[:k]


def user_gaps(user_id: str | None, k: int = 5) -> list[dict]:
    """The gaps of a user's M1 wardrobe ([] when the wardrobe cannot be read or is empty)."""
    if not user_id:
        return []
    try:
        from modules.m01_wardrobe import service
        from modules.m01_wardrobe.contract import ItemsRequest
        from shared.user_wardrobe import _run

        res = _run(service.items(ItemsRequest(user_id=user_id)))
        items = [it.model_dump(mode="json") for it in res.items]
    except Exception:  # noqa: BLE001 - M1 / database down: no gaps rather than fake ones
        return []
    if not items:
        return []
    gender = None
    try:
        from api.routes.auth import user_by_id

        gender = (user_by_id(user_id) or {}).get("gender")
    except Exception:  # noqa: BLE001
        pass
    return gaps_for(items, gender, k)
