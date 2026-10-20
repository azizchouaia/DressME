"""Suggest an outfit that keeps the challenge valid for the next day.

Greedy: for each slot, take the least-worn garment that passes the rules (rotation-friendly, BO1/BO3 spirit)
and still makes a wearable outfit (pipeline/outfit.py: one pair of shoes, one hat, a one-piece replaces
top and bottom…), then check the whole outfit with the outfit check and the rule engine.
Later this can call M2 (recommendation engine) with `locked_items` / excluded items instead;
the output format stays a list of item ids.
"""

from shared.schemas import Garment

from . import outfit as slots
from . import rules as rule_engine

SLOTS = [("top", ("top",)), ("bottom", ("bottom",)), ("shoes", ("shoes",))]


def run(rules: list[dict], wardrobe: list[Garment], previous: list[tuple[int, list[Garment]]]) -> list[str]:
    def ok(candidate: list[Garment]) -> bool:
        return not rule_engine.run(
            [r for r in rules if r["type"] not in ("min_items", "category_required", "local_brand")],
            candidate,
            previous,
        )

    used: dict[str, int] = {}  # times each piece was already worn in this challenge
    for _, items in previous:
        for g in items:
            used[g.item_id] = used.get(g.item_id, 0) + 1
    ranked = sorted(wardrobe, key=lambda g: (used.get(g.item_id, 0), g.wear_count, g.item_id))
    outfit: list[Garment] = []

    # required category first (e.g. Traditional Friday → a jebba replaces top + bottom)
    req = next((r for r in rules if r["type"] == "category_required"), None)
    if req:
        cats = set(req["params"].get("categories", []))
        piece = next(
            (g for g in ranked if (g.category.value in cats or (g.subcategory or "") in cats) and ok([g])),
            None,
        )
        if piece:
            outfit.append(piece)

    for _, cats in SLOTS:
        if any(g.category.value in cats for g in outfit):
            continue
        piece = next(
            (
                g
                for g in ranked
                if g.category.value in cats and g not in outfit and slots.fits(outfit, g) and ok(outfit + [g])
            ),
            None,
        )
        if piece:
            outfit.append(piece)

    if any(r["type"] == "local_brand" for r in rules) and not any(g.local_tag for g in outfit):
        for local in (g for g in ranked if g.local_tag and g not in outfit):
            s = slots.slot(local)
            rest = [  # a local one-piece (jebba) also replaces the top and the bottom
                g
                for g in outfit
                if slots.slot(g) != s and not (s == "one_piece" and slots.slot(g) in ("top", "bottom"))
            ]
            if slots.fits(rest, local) and ok(rest + [local]) and not slots.check(rest + [local]):
                outfit = rest + [local]
                break

    if slots.check(outfit) or rule_engine.run(rules, outfit, previous):
        return []
    return [g.item_id for g in outfit]
