"""F6.b unmet demand · F6.c price positioning · F6.d trends · funnel of one shop."""

from datetime import datetime, timedelta

import numpy as np

from modules.m07_local_catalogue import events as m7_events
from modules.m07_local_catalogue.paths import CONFIG as M7_CONFIG
from modules.m07_local_catalogue.taxonomy import SUBCATEGORIES, SUBCATEGORY_EN


def _piece_mask(catalogue, theme: dict) -> np.ndarray:
    mask = catalogue.available.copy()
    if theme["subcategory"]:
        mask &= catalogue.subcategory == theme["subcategory"]
    elif theme["category"]:
        mask &= catalogue.category == theme["category"]
    if theme["color"]:
        mask &= catalogue.color == theme["color"]
    if theme["gender"] in ("women", "men"):
        mask &= catalogue.gender != {"women": "men", "men": "women"}[theme["gender"]]
    return mask


def shop_mask(catalogue, shop: str | None) -> np.ndarray:
    if shop is None:
        return np.ones(len(catalogue), dtype=bool)
    return np.array([p["shop_name"] == shop for p in catalogue.products], dtype=bool)


def unmet(theme: dict, figures: dict, catalogue, shop: str | None, cfg: dict) -> dict:
    """F6.b: many searches x low coverage. Coverage mixes the shop's matching pieces in stock (catalogue)
    and the best FashionCLIP match between the theme and the shop's photos (looks, not just labels)."""
    in_shop = shop_mask(catalogue, shop)
    pieces = _piece_mask(catalogue, theme)
    n_shop, n_market = int((pieces & in_shop).sum()), int(pieces.sum())
    visual = 0.0
    if theme["centroid"] is not None:
        photos = in_shop & catalogue.has_embedding
        if photos.any():
            lo, hi = M7_CONFIG["visual_text_range"]
            best = float((catalogue.embeddings[photos] @ theme["centroid"]).max())
            visual = float(np.clip((best - lo) / (hi - lo), 0, 1))
    w = cfg["coverage_weights"]  # config.yaml dashboard.unmet
    coverage = w["stock"] * min(n_shop / cfg["full_stock"], 1.0) + w["visual"] * visual
    n, weak = figures["n_searches"], figures["weak_answer_rate"]
    if shop is None:
        hint = f"{n} searches for “{theme['label']}”, {n_market} piece(s) in stock in the catalogue"
    else:
        where = "none in the whole catalogue" if n_market == 0 else f"{n_market} in the whole catalogue"
        hint = f"{n} searches for “{theme['label']}”, {n_shop} in your shop ({where})"
    if weak >= 0.2:
        hint += f", {weak:.0%} of the searches without an exact piece"
    return {
        "theme_id": theme["theme_id"],
        "label": theme["label"],
        "n_searches": n,
        "zero_result_rate": figures["zero_result_rate"],
        "weak_answer_rate": weak,
        "products_in_shop": n_shop if shop else n_market,
        "products_in_market": n_market,
        "visual_coverage": round(visual, 3),
        "opportunity": round(n * (1 - coverage), 1),
        "hint": hint + ".",
    }


def prices(
    searches: list[dict], catalogue, shop: str | None, min_group: int, scope: set[str] | None = None
) -> tuple[list[dict], int]:
    """F6.c: budgets asked per type (parsed max price) vs the shop's prices in stock.
    `scope`: categories the shop sells (None = every category, for the whole market)."""
    budgets: dict[str, list[float]] = {}
    for s in searches:
        parsed = s["data"].get("parsed") or {}
        if scope is not None and SUBCATEGORIES.get(parsed.get("subcategory"), (None,))[0] not in scope:
            continue
        if parsed.get("subcategory") and parsed.get("max_price_tnd"):
            budgets.setdefault(parsed["subcategory"], []).append(float(parsed["max_price_tnd"]))
    in_shop = shop_mask(catalogue, shop) & catalogue.available & ~np.isnan(catalogue.price)
    rows, hidden = [], 0
    for sub, values in sorted(budgets.items(), key=lambda kv: -len(kv[1])):
        if len(values) < min_group:
            hidden += 1
            continue
        demand = np.quantile(values, [0.25, 0.5, 0.75])
        shop_prices = catalogue.price[in_shop & (catalogue.subcategory == sub)]
        row = {
            "subcategory": sub,
            "label": SUBCATEGORY_EN.get(sub, sub),
            "n_budgets": len(values),
            "demand_p25": round(float(demand[0]), 1),
            "demand_p50": round(float(demand[1]), 1),
            "demand_p75": round(float(demand[2]), 1),
        }
        if len(shop_prices):
            q = np.quantile(shop_prices, [0.25, 0.5, 0.75])
            cheapest = float(shop_prices.min())
            row |= {
                "shop_p25": round(float(q[0]), 1),
                "shop_p50": round(float(q[1]), 1),
                "shop_p75": round(float(q[2]), 1),
                # a budget is served when the shop has at least one piece of that type at or under it
                "served_share": round(sum(b >= cheapest for b in values) / len(values), 3),
            }
        else:
            row["served_share"] = 0.0
        rows.append(row)
    return rows, hidden


def trend(theme: dict, until: datetime, history_weeks: int, min_count: int, z_threshold: float) -> dict:
    """F6.d: searches of the last 7 days vs the weekly counts of the weeks before (z-score)."""
    times = [datetime.fromisoformat(m["ts"]) for m in theme["members"]]

    def count(weeks_back: int) -> int:
        end = until - timedelta(days=7 * weeks_back)
        return sum(end - timedelta(days=7) < t <= end for t in times)

    last = count(0)
    before = np.array([count(w) for w in range(1, history_weeks + 1)], dtype=float)
    mean, std = float(before.mean()), float(before.std())
    z = (last - mean) / max(std, 1.0)
    return {
        "theme_id": theme["theme_id"],
        "label": theme["label"],
        "last_7_days": last,
        "weekly_mean_before": round(mean, 2),
        "z": round(z, 2),
        "growth": round(last / mean - 1, 2) if mean > 0 else float(last),
        "rising": last >= min_count and z >= z_threshold,
    }


def funnel(events: list[dict], shop: str) -> dict:
    """Impressions / views / clicks of the shop (M7 log summary) and its rank among shops by clicks."""
    shops = m7_events.summary(events)["shops"] if events else {}
    row = shops.get(shop, {"impressions": 0, "views": 0, "clicks": 0, "ctr": 0.0})
    by_clicks = sorted(shops, key=lambda s: -shops[s]["clicks"])
    return {**row, "ctr": round(row["ctr"], 4), "rank": by_clicks.index(shop) + 1 if shop in shops else None}
