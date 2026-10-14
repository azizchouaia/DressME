"""Real implementation of M2 (same signatures as mock.py).
Heavy imports stay lazy so the API boots without torch."""

from __future__ import annotations

import datetime as dt
from functools import lru_cache

from .contract import CompletePayload, RecommendPayload, RemixPayload, ScorePayload, SwapPayload


@lru_cache(maxsize=1)
def engine():
    import json

    from .engine import artifacts
    from .engine.attributes import AttributeScorer
    from .engine.outfit_transformer import OutfitTransformer
    from .engine.recommender import Recommender

    cal = json.load(open(artifacts.COMPAT_CALIBRATION)) if artifacts.COMPAT_CALIBRATION.exists() else None
    return Recommender(OutfitTransformer(), AttributeScorer(), cal)


def _setup(user_id: str | None, p):
    """payload -> (all items, filtered items, ctx, weather source)."""
    import numpy as np

    from .engine import wardrobe
    from .engine.recommender import Ctx
    from .engine.weather import get_weather, is_rainy

    c, o = p.context, p.options
    today = c.date or dt.date.today()
    if p.items is not None:
        items = wardrobe.from_payload(p.items)
        demo = False
    else:
        items = wardrobe.load_demo(user_id)
        demo = True
    log = [e.model_dump() for e in p.wear_log]
    if not log and demo:
        log = wardrobe.demo_wear_log(user_id or "demo_f", items, today)

    # wear log -> last worn date per piece + pairs already worn together
    last: dict[str, dt.date] = {}
    pairs: set[tuple[str, str]] = set()
    counts: dict[str, int] = {}
    for e in log:
        if e["date"] > today:
            continue
        ids = sorted(set(e["item_ids"]))
        for i in ids:
            last[i] = max(last.get(i, e["date"]), e["date"])
            counts[i] = counts.get(i, 0) + 1
        pairs.update((a, b) for k, a in enumerate(ids) for b in ids[k + 1 :])
    for it in items:
        if it.item_id in last:
            it.last_worn = max(it.last_worn or last[it.item_id], last[it.item_id])
            it.wear_count = max(it.wear_count, counts[it.item_id])

    if c.weather is not None:
        weather, source = c.weather.model_dump(), "request"
    else:
        weather, source = get_weather(c.city, today)
    ctx = Ctx(
        occasion=c.occasion,
        mood=c.mood,
        temp_c=weather["temp_c"],
        condition=weather["condition"],
        rainy=is_rainy(weather["condition"]),
        today=today,
        rotation_window=o.rotation_window_days,
        forgotten_after=o.forgotten_after_days,
        allow_outerwear=o.allow_outerwear,
        style_vector=np.asarray(o.style_vector, np.float32) if o.style_vector else None,
        worn_pairs=pairs,
        has_history=bool(log),
    )
    usable = engine().prepare(items, ctx, set(o.exclude_item_ids))
    return items, usable, ctx, source


def _result(user_id, ranked, ctx, source) -> dict:
    from .engine.recommender import to_outfit

    used = {i.item_id: i.public() for r in ranked for i in r["items"]}
    return {
        "result": {
            "outfits": [to_outfit(r, ctx, user_id) for r in ranked],
            "items": used,
            "context": {
                "occasion": ctx.occasion,
                "date": ctx.today.isoformat(),
                "weather": {"temp_c": ctx.temp_c, "condition": ctx.condition},
            },
            "weather_source": source,
        },
        "mocked": False,
    }


def recommend(req: dict) -> dict:
    p = RecommendPayload.model_validate(req.get("payload") or {})
    _, usable, ctx, src = _setup(req.get("user_id"), p)
    return _result(req.get("user_id"), engine().recommend(usable, ctx, p.options.n), ctx, src)


def remix(req: dict) -> dict:
    p = RemixPayload.model_validate(req.get("payload") or {})
    _, usable, ctx, src = _setup(req.get("user_id"), p)
    base = set(p.base_item_ids)
    if not base:  # remix of today's outfit by default
        top = engine().recommend(usable, ctx, 1)
        base = {i.item_id for i in top[0]["items"]} if top else set()
    ranked = engine().recommend(usable, ctx, p.options.n, remix=True, avoid=base)
    return _result(req.get("user_id"), ranked, ctx, src)


def complete(req: dict) -> dict:
    p = CompletePayload.model_validate(req.get("payload") or {})
    items, usable, ctx, src = _setup(req.get("user_id"), p)
    by_id = {i.item_id: i for i in items}
    pinned = [by_id[i] for i in p.pinned_item_ids if i in by_id]
    usable = [i for i in usable if i.item_id not in p.pinned_item_ids]
    return _result(req.get("user_id"), engine().complete(usable, ctx, pinned, p.options.n), ctx, src)


def swap(req: dict) -> dict:
    p = SwapPayload.model_validate(req.get("payload") or {})
    items, usable, ctx, src = _setup(req.get("user_id"), p)
    by_id = {i.item_id: i for i in items}
    current = [by_id[i] for i in p.item_ids if i in by_id]
    n = p.options.n if "n" in p.options.model_fields_set else 5
    return _result(req.get("user_id"), engine().swap(usable, ctx, current, p.slot, n), ctx, src)


def demo_wardrobe(user_id: str) -> dict:
    """Demo page only: the demo wardrobe with attributes and last-worn dates."""
    from .engine import wardrobe

    items, _, ctx, _ = _setup(user_id, RecommendPayload())
    return {
        "users": wardrobe.demo_users(),
        "today": ctx.today.isoformat(),
        "items": [i.public() for i in items],
    }


def score(req: dict) -> dict:
    p = ScorePayload.model_validate(req.get("payload") or {})
    items, _, ctx, src = _setup(req.get("user_id"), p)
    by_id = {i.item_id: i for i in items}
    outfits = [[by_id[i] for i in o if i in by_id] for o in p.outfits]
    return _result(req.get("user_id"), engine().score([o for o in outfits if len(o) >= 2], ctx), ctx, src)
