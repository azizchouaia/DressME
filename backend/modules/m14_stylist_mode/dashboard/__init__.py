"""F6 · boutique demand dashboard: what users search, at what budget, where, and what nobody sells.

Built from M7's search / click log (and the simulator's, said in `simulated_share`). Aggregates only:
no user id ever leaves this module, and a figure built from fewer than `min_group` searches is hidden.
"""

from datetime import UTC, datetime, timedelta

from . import data, metrics, themes


async def build(
    shop: str | None,
    config: dict,
    catalogue,
    encoder,
    days: int | None = None,
    sources: list[str] | None = None,
    until: datetime | None = None,
) -> dict:
    cfg = config["dashboard"]
    days = days or cfg["period_days"]
    sources = sources or cfg["sources"]
    until = until or datetime.now(UTC)
    since = until - timedelta(days=days)
    history_weeks = cfg["trends"]["history_weeks"]
    window_start = min(since, until - timedelta(days=7 * (history_weeks + 1)))
    min_group = config["min_group"]

    events = data.load(sources, window_start, until)
    period_events = [e for e in events if datetime.fromisoformat(e["ts"]) > since]
    all_searches = data.searches(events)
    period = data.searches(period_events)

    # Themes on the trend window (so trends and themes are the same groups), figures on the period.
    logs = tuple(str(data.log_paths().get(s)) for s in sources)
    cache_key = (logs, (until - window_start).days)
    groups, _, method = themes.build(all_searches, encoder, config, cache_key)
    period_ids = {s["event_id"] for s in period}
    not_understood = sum(themes.prompt_of(s) is None for s in period)
    pieces = {p["product_id"]: (p["subcategory"], p.get("color") or None) for p in catalogue.products}
    # A shop's unmet demand and prices only cover the categories it sells (no "shirts" for a shoe shop).
    scope = {p["category"] for p in catalogue.products if p["shop_name"] == shop} if shop else None
    rows, unmet, trends, hidden = [], [], [], 0
    for theme in groups:
        members = [m for m in theme["members"] if m["event_id"] in period_ids]
        if len(members) < min_group:
            hidden += 1
            continue
        figures = themes.stats(
            theme, members, len(period), pieces, cfg["unmet"]["low_match"], cfg["themes"]["examples"]
        )
        rows.append(figures)
        if scope is None or theme["category"] in scope:
            unmet.append(metrics.unmet(theme, figures, catalogue, shop, cfg["unmet"]))
        trends.append(
            metrics.trend(
                theme, until, history_weeks, cfg["trends"]["min_count"], cfg["trends"]["z_threshold"]
            )
        )
    prices, hidden_prices = metrics.prices(period, catalogue, shop, min_group, scope)
    simulated = sum(s["_source"] == "simulated" for s in period)
    return {
        "shop": shop,
        "period_days": days,
        "since": since,
        "until": until,
        "n_searches": len(period),
        "simulated_share": round(simulated / len(period), 3) if period else 0.0,
        "funnel": metrics.funnel(period_events, shop) if shop else None,
        "themes": sorted(rows, key=lambda r: -r["n_searches"]),
        "unmet": sorted(unmet, key=lambda r: -r["opportunity"])[:10],
        "prices": prices,
        "trends": sorted(trends, key=lambda r: -r["z"]),
        "not_understood": not_understood,
        "hidden_groups": hidden + hidden_prices,
        "method": {
            "themes": method,
            "unmet": "categories the shop sells only; opportunity = searches x (1 - coverage); "
            f"coverage = {cfg['unmet']['coverage_weights']['stock']} x pieces in stock "
            f"({cfg['unmet']['full_stock']} = full) + {cfg['unmet']['coverage_weights']['visual']} x best "
            "FashionCLIP match of the shop's photos with the theme",
            "prices": "budgets = parsed max price per type; served = budget >= the shop's cheapest piece",
            "trends": f"last 7 days vs the {history_weeks} weeks before, z-score (std floored at 1)",
            "privacy": f"aggregates only; groups under {min_group} searches hidden",
            "sources": ", ".join(sources),
        },
    }
