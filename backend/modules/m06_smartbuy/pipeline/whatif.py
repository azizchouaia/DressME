"""Idea 8 — counterfactuals: 'what would change the answer'.

Re-runs the decision on the same facts with one thing changed (price, need, number owned).
"""

from .decide import ORDER, decide


def _with(facts, **kw):
    return {**facts, **kw}


def explain(facts: dict, cfg: dict, model: dict | None, offset: int, current: str) -> list[str]:
    out = []
    price = facts["price"]
    sub = facts["subcategory"]
    if facts["red"]["is_duplicate"]:
        return [f"Only worth it if it replaces your {facts['red']['duplicate_of']['label'].lower()}."]
    # price
    if price:
        if current != "buy":
            for p in range(int(price) - 5, 0, -5):
                v = decide(_with(facts, price=float(p)), cfg, model, offset)["verdict"]
                if ORDER[v] > ORDER[current]:
                    out.append(f"{v.upper()} if the price drops to {p} TND or less.")
                    break
        else:
            for p in range(int(price) + 5, int(price) * 3, 5):
                v = decide(_with(facts, price=float(p)), cfg, model, offset)["verdict"]
                if ORDER[v] < ORDER["buy"]:
                    out.append(f"Still BUY up to about {p - 5} TND; above that it becomes {v.upper()}.")
                    break
    # need / gap
    if not facts["gap"] and current != "buy":
        v = decide(_with(facts, gap="occasion"), cfg, model, offset)["verdict"]
        if ORDER[v] > ORDER[current]:
            out.append(f"{v.upper()} if you need it for a specific occasion.")
    # too many of the same type
    mx = cfg.get("max_same_type", 99)
    if facts["n_same"] >= mx and current != "buy":
        v = decide(_with(facts, n_same=mx - 1), cfg, model, offset)["verdict"]
        if ORDER[v] > ORDER[current]:
            out.append(f"{v.upper()} if you let go of one of your {facts['n_same']} {sub}s.")
    # more outfits (other modules: e.g. after buying matching pieces)
    if facts["unl"]["new_outfits"] < 3 and current == "skip":
        out.append("It matches few of your clothes: check what you'd wear it with first.")
    return out[:3]
