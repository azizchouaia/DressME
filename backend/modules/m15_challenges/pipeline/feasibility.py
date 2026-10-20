"""Can this wardrobe complete the challenge? Score in [0, 1] + a sentence the user understands.

Outfit model: (top + bottom | dress | traditional) + shoes.
1. Keep only the garments that pass the item-level rules (colour theme in "all" mode, local brand…).
2. If the challenge forbids repeats, count how many *disjoint* outfits the filtered wardrobe can make:
       disjoint = min( min(tops, bottoms) + one_pieces , shoes )
   feasibility = min(1, disjoint / days).
3. Otherwise one valid outfit is enough (feasibility 1 or 0), except for a capsule limit,
   where the capsule must contain at least one complete outfit.
"""

from shared.schemas import Garment

from .rules import dominant_color

ONE_PIECE = {"dress", "traditional"}


def _counts(items: list[Garment]) -> dict[str, int]:
    c = {"top": 0, "bottom": 0, "one_piece": 0, "shoes": 0}
    for g in items:
        cat = g.category.value
        if cat == "top":
            c["top"] += 1
        elif cat == "bottom":
            c["bottom"] += 1
        elif cat in ONE_PIECE:
            c["one_piece"] += 1
        elif cat == "shoes":
            c["shoes"] += 1
    return c


def disjoint_outfits(items: list[Garment]) -> int:
    c = _counts(items)
    return min(min(c["top"], c["bottom"]) + c["one_piece"], c["shoes"])


def _filter(rules: list[dict], items: list[Garment]) -> list[Garment]:
    out = items
    for r in rules:
        p = r.get("params", {})
        if r["type"] == "color_theme" and p.get("mode", "all") == "all":
            colors = {c.lower() for c in p.get("colors", [])}
            out = [g for g in out if dominant_color(g) in colors]
    return out


def run(rules: list[dict], days: int, wardrobe: list[Garment]) -> tuple[float, str]:
    types = {r["type"] for r in rules}
    params = {r["type"]: r.get("params", {}) for r in rules}
    pool = _filter(rules, wardrobe)

    # requirements that must hold on every day
    if "category_required" in types:
        cats = set(params["category_required"].get("categories", []))
        n = sum(1 for g in pool if g.category.value in cats or (g.subcategory or "") in cats)
        needed = days if "no_repeat" in types else 1
        if n == 0:
            return 0.0, f"You have no {' / '.join(sorted(cats))} piece yet."
        if n < needed:
            return n / needed, f"You have {n} {' / '.join(sorted(cats))} piece(s) for {needed} days."
    if "local_brand" in types:
        n = sum(1 for g in pool if g.local_tag)
        if n == 0:
            return 0.0, "No piece from a Tunisian brand in your wardrobe yet."

    if "no_repeat" in types:
        k = disjoint_outfits(pool)
        score = min(1.0, k / days)
        if score >= 1:
            return 1.0, f"You can make {k} different outfits: enough for {days} days."
        c = _counts(pool)
        bottleneck = min(
            ("tops", c["top"] + c["one_piece"]),
            ("bottoms", c["bottom"] + c["one_piece"]),
            ("shoes", c["shoes"]),
            key=lambda t: t[1],
        )
        return round(score, 2), f"Only {k} different outfits possible ({bottleneck[0]} are the limit)."

    if "capsule_limit" in types:
        cap = int(params["capsule_limit"].get("max_distinct", 10))
        ok = disjoint_outfits(pool) >= 1 and len(pool) >= 3
        return (
            (1.0, f"Pick {cap} pieces and remix them for {days} days.")
            if ok
            else (0.0, "Not enough pieces to build a capsule.")
        )

    ok = disjoint_outfits(pool) >= 1
    return (
        (1.0, "Your wardrobe has what this challenge needs.")
        if ok
        else (0.0, "No complete outfit matches this challenge.")
    )
