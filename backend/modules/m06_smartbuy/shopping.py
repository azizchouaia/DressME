"""BO5 own task: wardrobe gap shopping list.

For each missing piece (from the user's goals + M5 gaps): pick the colour that creates the most outfits
with what the user owns (M2), the usual local price, and local buy links (M13). Most useful first.
"""

from modules.m13_partner_links import service as partners

from . import goals as goals_mod
from . import synthetic as syn


def _options(gap: dict) -> list[str]:
    cols = gap.get("colours") or syn.TYPE_COLOURS[gap["subcategory"]]
    return [c for c in cols if c in syn.TYPE_COLOURS[gap["subcategory"]]] or syn.TYPE_COLOURS[gap["subcategory"]]


def _m5_gaps(gaps: list[str]) -> list[dict]:
    out = []
    for g in gaps:
        words = g.lower().split()
        sub = words[-1]
        if sub not in syn.TYPES:
            continue
        cols = None if words[0] == "any" else words[0].split("|")
        out.append({"gap": g, "goal": None, "goal_name": "your wardrobe gaps", "subcategory": sub, "colours": cols,
                    "have": 0, "target": 1, "missing": 1})
    return out


def shopping_list(agent, user_id: str, k: int = 8) -> list[dict]:
    cl = agent.clients
    items = cl.items(user_id)
    user_goals = cl.goals(user_id)
    gaps = goals_mod.goal_gaps(user_goals, items)
    seen = {g["gap"] for g in gaps}
    gaps += [g for g in _m5_gaps(cl.gaps(user_id)) if g["gap"] not in seen]
    budget = user_goals.get("budget", {}) if "budget" in user_goals.get("templates", []) else {}
    left = budget["monthly_tnd"] - budget.get("spent_tnd", 0) if budget.get("monthly_tnd") else None
    rows = []
    for g in gaps:
        sub = g["subcategory"]
        best = max(_options(g), key=lambda c: len(cl.recommend_with(user_id, {
            "id": f"custom:{sub}:{c}", "category": syn.TYPES[sub][0], "subcategory": sub, "colour": c})))
        n = len(cl.recommend_with(user_id, {"id": f"custom:{sub}:{best}", "category": syn.TYPES[sub][0],
                                            "subcategory": sub, "colour": best}))
        price = agent.typical.get(sub)
        rows.append({
            "piece": syn.label(f"{best} {sub}"), "subcategory": sub, "colour": best,
            "why": f"{g['goal_name']}: {g['have']} of {g['target']}" if g["goal"] else "listed in your wardrobe gaps",
            "goal": g["goal"], "new_outfits": n, "typical_price_tnd": price,
            "within_budget": None if left is None or price is None else price <= left,
            "links": partners.links(agent.shops, sub, best, left, 2, one_per_shop=True),
        })
    rows.sort(key=lambda r: (r["within_budget"] is False, -r["new_outfits"]))
    return rows[:k]
