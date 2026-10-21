"""if/else · is this a wearable outfit? Checked before the challenge rules, for every challenge.

Each garment goes to one body slot. A real outfit has at most one piece per slot (one pair of shoes, one hat,
one bag…), a one-piece (dress, jebba, blouza) replaces the top and the bottom, and the body is covered:
a top and a bottom, or a one-piece. A light layer (jacket, blazer, kachabia, sefsari) can go over it.
"""

from shared.schemas import Garment

# slot → (label used in messages, max pieces)
SLOTS: dict[str, tuple[str, int]] = {
    "one_piece": ("one-piece (dress, jebba, blouza)", 1),
    "top": ("top", 1),
    "bottom": ("bottom", 1),
    "layer": ("jacket or coat", 1),
    "shoes": ("pair of shoes", 1),
    "hat": ("hat", 1),
    "bag": ("bag", 1),
    "scarf": ("scarf or fouta", 1),
    "accessory": ("other accessory", 2),
}
LAYER_WORDS = ("kachabia", "sefsari", "burnous", "jacket", "coat", "blazer", "cardigan")
HAT_WORDS = ("hat", "cap", "chechia", "beanie", "beret")
BAG_WORDS = ("bag", "koffa", "purse", "backpack", "tote")
SCARF_WORDS = ("scarf", "fouta", "shawl", "foulard")


def slot(g: Garment) -> str:
    c, s = g.category.value, (g.subcategory or "").lower()
    if c == "dress":
        return "one_piece"
    if c == "traditional":
        return "layer" if any(w in s for w in LAYER_WORDS) else "one_piece"
    if c == "outerwear":
        return "layer"
    if c in ("top", "bottom", "shoes"):
        return c
    if any(w in s for w in HAT_WORDS):
        return "hat"
    if any(w in s for w in BAG_WORDS):
        return "bag"
    if any(w in s for w in SCARF_WORDS):
        return "scarf"
    return "accessory"


def _name(g: Garment) -> str:
    return g.subcategory or g.category.value


def check(today: list[Garment]) -> list[str]:
    """Problems that make the outfit impossible to wear (empty list = wearable)."""
    by: dict[str, list[Garment]] = {}
    for g in today:
        by.setdefault(slot(g), []).append(g)
    out: list[str] = []
    for s, items in by.items():
        label, most = SLOTS[s]
        if len(items) > most:
            names = ", ".join(_name(g) for g in items)
            out.append(f"only {most} {label} at a time ({names})")
    if by.get("one_piece"):
        covered = [g for g in by.get("top", []) + by.get("bottom", [])]
        if covered:
            out.append(
                f"{_name(by['one_piece'][0])} already covers top and bottom: remove "
                + ", ".join(_name(g) for g in covered)
            )
    elif today and not (by.get("top") and by.get("bottom")):
        missing = "a bottom" if by.get("top") else "a top" if by.get("bottom") else "a top and a bottom"
        out.append(f"an outfit needs {missing}, or a one-piece (dress, jebba)")
    return out


def fits(outfit: list[Garment], g: Garment) -> bool:
    """Can g be added to a partial outfit without breaking a slot? (used by the next-day suggestion)"""
    s = slot(g)
    taken = [slot(x) for x in outfit]
    if taken.count(s) >= SLOTS[s][1]:
        return False
    if s == "one_piece" and ("top" in taken or "bottom" in taken):
        return False
    return not (s in ("top", "bottom") and "one_piece" in taken)
