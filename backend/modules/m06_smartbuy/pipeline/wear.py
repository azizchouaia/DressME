"""Idea 5 — predict how often the piece will be worn, from similar pieces you already own.

predicted wears / year = similarity-weighted average of 'wear_count' (wears per year) of the closest
owned pieces in the same category. Needs wear data (wear log M3, or 'wear_count' in the dataset).
"""


def predict(neighbours: list[dict], items_by_id: dict, category: str, price: float | None) -> dict:
    pts = []
    for n in neighbours:
        it = items_by_id.get(n["item_id"])
        if it and it.get("category") == category and it.get("wear_count") is not None and n["similarity"] > 0.3:
            pts.append((n["similarity"], it["wear_count"]))
    if not pts:
        return {"predicted_wears": None, "cost_per_wear": None}
    wsum = sum(s for s, _ in pts)
    wears = sum(s * w for s, w in pts) / wsum
    cpw = round(price / max(wears, 1), 2) if price else None
    return {"predicted_wears": round(wears), "cost_per_wear": cpw}
