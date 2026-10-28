"""Step 4 — weighted score 0-100 and verdict."""


def compute(red: dict, unlock: dict, gap: str | None, price: float | None, cfg: dict) -> dict:
    w = cfg["weights"]
    new_outfits = min(unlock["new_outfits"] / cfg["outfits_for_max_score"], 1.0)
    gap_fill = 1.0 if gap else 0.0
    novelty = red["novelty"]
    if price is None or unlock["new_outfits"] == 0:
        cpo, price_value = None, 0.5 if price is None else 0.0
    else:
        cpo = price / unlock["new_outfits"]
        price_value = min(cfg["target_cost_per_outfit_tnd"] / cpo, 1.0)
    parts = {"new_outfits": new_outfits, "gap_fill": gap_fill, "novelty": novelty, "price_value": price_value}
    score = round(100 * sum(w[k] * v for k, v in parts.items()))
    return {"score": score, "breakdown": {k: round(v, 2) for k, v in parts.items()},
            "cost_per_outfit": None if cpo is None else round(cpo, 1)}


def verdict(score: int, is_duplicate: bool, cfg: dict, same_type_count: int = 0) -> str:
    if is_duplicate:
        return "skip"
    if score >= cfg["buy_threshold"]:
        # Decision (BO5): owning too many of the same type caps BUY at THINK
        return "think" if same_type_count >= cfg.get("max_same_type", 99) else "buy"
    if score < cfg["skip_threshold"]:
        return "skip"
    return "think"


def reasons(red, unlock, gap, cpo, label_of, same_type_count=0, subcategory="", cfg=None) -> list[str]:
    r = []
    if red["is_duplicate"]:
        r.append(f"you already own almost the same piece ({label_of(red['duplicate_of'])})")
    elif red["similar"]:
        r.append(f"close to your {label_of(red['similar'][0])}")
    else:
        r.append("nothing similar in your wardrobe")
    n = unlock["new_outfits"]
    r.append(f"creates {n} new outfit{'s' if n != 1 else ''}" if n else "matches almost nothing you own")
    if gap:
        r.append(f"fills a gap: {gap}")
    if cpo is not None:
        r.append(f"{cpo} TND per new outfit")
    if cfg and same_type_count >= cfg.get("max_same_type", 99):
        r.insert(0, f"you already own {same_type_count} {subcategory}s")
    return r
