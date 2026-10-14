"""Personal goals (read side for BO5). The goals themselves belong to M5 (style profile, BO4):
until M5 ships them, they come from the mock store ml/data/bo5/goals.json.

A user picks one or more goal TEMPLATES (+ a budget). From them we compute:
- goal gaps : pieces the wardrobe is missing to reach the goal ("navy|black blazer", "colourful top")
- goal fit  : -1..+1, does THIS candidate help or break the user's goals (used by the decision)
"""

from . import synthetic as syn

NEUTRAL = {c for c, (_, n) in syn.COLOURS.items() if n}

TEMPLATES = {
    "work": {
        "name": "Work wardrobe",
        "description": "Smart pieces for the office: blazers, shirts, tailored trousers, loafers.",
        "targets": [("blazer", ["navy", "black", "grey"], 2), ("shirt", ["white", "blue", "navy"], 4),
                    ("trousers", ["black", "grey", "navy", "beige"], 2), ("loafers", ["brown", "black"], 1)],
    },
    "casual": {
        "name": "Casual weekend",
        "description": "Easy everyday basics: jeans, t-shirts, sneakers, a jacket.",
        "targets": [("jeans", None, 2), ("t-shirt", None, 4), ("sneakers", ["white", "black"], 1), ("jacket", None, 1)],
    },
    "minimalist": {
        "name": "Minimalist (30 pieces)",
        "description": "Fewer, neutral pieces that all combine. At most 30 pieces, 3 of a type.",
        "max_pieces": 30, "max_per_type": 3, "neutral_only": True,
    },
    "more_colour": {
        "name": "More colour",
        "description": "At least one coloured piece in tops, bottoms and outerwear.",
        "colour_in": ["top", "bottom", "outerwear"],
    },
    "budget": {
        "name": "Monthly budget",
        "description": "Stay under a monthly spending limit (TND).",
        "uses_budget": True,
    },
}


def _matches(item: dict, sub: str, colours) -> bool:
    return item["subcategory"] == sub and (colours is None or item["colour"] in colours)


def goal_gaps(goals: dict, items: list[dict]) -> list[dict]:
    """Missing pieces for the user's goals, most missing first."""
    out = []
    for gid in goals.get("templates", []):
        t = TEMPLATES.get(gid, {})
        for sub, colours, qty in t.get("targets", []):
            have = sum(_matches(i, sub, colours) for i in items)
            if have < qty:
                key = f"{'|'.join(colours) if colours else 'any'} {sub}"
                out.append({"gap": key, "goal": gid, "goal_name": t["name"], "subcategory": sub,
                            "colours": colours, "have": have, "target": qty, "missing": qty - have})
        for cat in t.get("colour_in", []):
            if not any(i["category"] == cat and i["colour"] not in NEUTRAL for i in items):
                sub = {"top": "shirt", "bottom": "skirt", "outerwear": "jacket"}[cat]
                out.append({"gap": f"colourful {cat}", "goal": gid, "goal_name": t["name"], "subcategory": sub,
                            "colours": sorted(c for c in syn.TYPE_COLOURS[sub] if c not in NEUTRAL), "have": 0,
                            "target": 1, "missing": 1, "category": cat})
    return sorted(out, key=lambda g: -g["missing"])


def goal_fit(goals: dict, items: list[dict], cand: dict, price: float | None) -> dict:
    """-> {score -1..1, reasons, fills (goal name), over_budget, budget_left}. Over budget caps BUY at THINK."""
    score, reasons, fills, over, left = 0.0, [], None, False, None
    if not goals.get("templates"):
        return {"score": 0.0, "reasons": [], "fills": None, "over_budget": False, "budget_left": None}
    for g in goal_gaps(goals, items):
        if g["subcategory"] == cand["subcategory"] and (g["colours"] is None or cand["colour"] in g["colours"]):
            score += 1.0
            fills = g["goal_name"]
            reasons.append(f"helps your goal '{g['goal_name']}': {g['have']} of {g['target']} {cand['subcategory']}s")
            break
        if g["gap"].startswith("colourful") and cand["category"] == g.get("category") and cand["colour"] not in NEUTRAL:
            score += 0.7
            fills = g["goal_name"]
            reasons.append(f"adds colour to your {g['category']}s (goal '{g['goal_name']}')")
            break
    for gid in goals["templates"]:
        t = TEMPLATES.get(gid, {})
        if t.get("max_pieces") and len(items) >= t["max_pieces"]:
            score -= 1.0
            reasons.append(f"minimalist goal: you already own {len(items)} pieces (max {t['max_pieces']})")
        if t.get("max_per_type") and sum(i["subcategory"] == cand["subcategory"] for i in items) >= t["max_per_type"]:
            score -= 0.7
            reasons.append(f"minimalist goal: max {t['max_per_type']} {cand['subcategory']}s")
        if t.get("neutral_only") and cand["colour"] not in NEUTRAL:
            score -= 0.4
            reasons.append("minimalist goal: neutral colours combine best")
        if t.get("uses_budget") and price:
            b = goals.get("budget", {})
            limit, spent = b.get("monthly_tnd"), b.get("spent_tnd", 0)
            if limit:
                left = max(limit - spent, 0)
                if spent + price > limit:
                    over = True
                    score -= 1.0
                    reasons.append(f"over your monthly budget: {spent:.0f} + {price:.0f} > {limit:.0f} TND")
                else:
                    reasons.append(f"within budget: {limit - spent - price:.0f} TND left this month")
    return {"score": max(-1.0, min(1.0, score)), "reasons": reasons, "fills": fills,
            "over_budget": over, "budget_left": left}
