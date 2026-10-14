"""Step 1 — do I already own something similar? (uses M1 /similar)

Decision (BO5): a DUPLICATE = same type (subcategory) AND same colour AND similarity >= threshold.
Same type in another colour is NOT a duplicate: it only lowers novelty.
"""


def check(neighbours: list[dict], cand: dict, cfg: dict) -> dict:
    same_cat = [n for n in neighbours if n.get("category") == cand["category"]]
    same_type_colour = [n for n in same_cat
                        if n.get("subcategory") == cand["subcategory"] and n.get("colour") == cand["colour"]]
    top_same = max((n["similarity"] for n in same_type_colour), default=0.0)
    top_other = max((n["similarity"] for n in same_cat if n not in same_type_colour), default=0.0)
    novelty = min(1.0 - top_same, 1.0 - cfg["other_colour_novelty_factor"] * top_other)
    return {
        "max_similarity": max(top_same, top_other),
        "novelty": round(max(novelty, 0.0), 3),
        "is_duplicate": top_same >= cfg["duplicate_threshold"],
        "duplicate_of": next((n for n in same_type_colour if n["similarity"] >= cfg["duplicate_threshold"]), None),
        "similar": [n for n in same_cat if n["similarity"] >= cfg["similar_threshold"]],
    }
