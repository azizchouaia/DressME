"""Bridge to M2 (recommendation engine, owner BO1/BO2): about 20 candidate outfits for a context.

config m02.source:
  mock   : built in (M2 is not merged yet). Random valid outfits from the user's active M1 items:
           top + bottom or a one-piece (dress / traditional), + shoes, + outerwear when it is cold.
           Drops items of another size and warm items when it is hot.
  module : modules.m02_recommendation (envelope {user_id, payload} -> {result: {outfits}}). M5 sends the
           user's taste vector (options.style_vector). Outfits whose pieces are not the user's M1 items (e.g.
           M2's demo wardrobe) cannot be scored by M5: they are dropped, and when none is left M5 falls back
           to the mock (with a warning).
Outfit = {outfit_id, item_ids, score, score_breakdown} (team rule).
"""

import hashlib
import inspect
import logging
import random
from dataclasses import dataclass, field

from .attributes import normalise_size, warmth
from .config import get_config

log = logging.getLogger(__name__)


@dataclass
class Outfit:
    item_ids: list[str]
    outfit_id: str = ""
    score: float = 0.0
    score_breakdown: dict = field(default_factory=dict)

    def __post_init__(self):
        self.outfit_id = self.outfit_id or outfit_id_for(self.item_ids)


def outfit_id_for(item_ids: list[str]) -> str:
    return "out_" + hashlib.sha1("|".join(sorted(item_ids)).encode()).hexdigest()[:12]


def _size_ok(item, size: str | None, sized: set[str]) -> bool:
    want, have = normalise_size(size), normalise_size(item.size)
    category = getattr(item.category, "value", item.category)
    return not (want and have and category in sized and want != have)


def mock_outfits(
    items: list,
    temp_c: float,
    size: str | None = None,
    n: int | None = None,
    rng: random.Random | None = None,
) -> list[Outfit]:
    cfg = get_config().m02
    rng = rng or random.Random()
    n = n or cfg.n_candidates
    sized = set(cfg.sized_categories)
    pool = [i for i in items if getattr(i.status, "value", i.status) == "active" and _size_ok(i, size, sized)]
    if temp_c > cfg.hot_temp:
        pool = [i for i in pool if warmth(i) < cfg.warm_item]
    by_cat: dict[str, list] = {}
    for i in pool:
        by_cat.setdefault(getattr(i.category, "value", i.category), []).append(i)
    tops, bottoms = by_cat.get("top", []), by_cat.get("bottom", [])
    bases = [[t, b] for t in tops for b in bottoms]
    bases += [[d] for d in by_cat.get("dress", []) + by_cat.get("traditional", [])]
    if not bases:
        return []
    shoes, outer = by_cat.get("shoes", []), by_cat.get("outerwear", [])
    seen: dict[str, Outfit] = {}
    for _ in range(n * 8):
        if len(seen) >= n:
            break
        pieces = list(rng.choice(bases))
        if shoes:
            pieces.append(rng.choice(shoes))
        if outer and temp_c < cfg.outer_below and rng.random() < 0.6:
            pieces.append(rng.choice(outer))
        outfit = Outfit([p.item_id for p in pieces])
        if outfit.outfit_id not in seen:
            compat = round(rng.uniform(0.55, 0.95), 3)
            weather_fit = round(
                1 - abs(sum(warmth(p) for p in pieces) / len(pieces) - min(max((25 - temp_c) / 25, 0), 1)), 3
            )
            outfit.score_breakdown = {"compatibility": compat, "weather_fit": weather_fit}
            outfit.score = round(0.7 * compat + 0.3 * weather_fit, 3)
            seen[outfit.outfit_id] = outfit
    return sorted(seen.values(), key=lambda o: -o.score)


async def _from_module(
    user_id: str, context: dict, n: int, style_vector: list[float] | None = None
) -> list[Outfit]:
    from modules.m02_recommendation import router as m02_router

    impl = m02_router._impl()
    options = {"n": min(n, 10)}
    if style_vector:
        options["style_vector"] = list(style_vector)  # M2's style_match criterion (taste learnt by M5)
    payload = {
        "context": {
            "occasion": get_config().context.canonical(context.get("occasion", "casual")),
            "weather": {
                "temp_c": context.get("temp_c", 20),
                "condition": "rain" if context.get("rain") else "clear",
            },
        },
        "options": options,
    }
    res = impl.recommend({"user_id": user_id, "payload": payload})
    if inspect.isawaitable(res):
        res = await res
    res = res if isinstance(res, dict) else res.model_dump()
    outfits = (res.get("result") or {}).get("outfits") or []
    return [
        Outfit(
            item_ids=list(o.get("items") or o.get("item_ids") or []),
            outfit_id=o.get("outfit_id", ""),
            score=float(o.get("score") or 0.0),
            score_breakdown=o.get("score_breakdown") or {},
        )
        for o in outfits
        if o.get("items") or o.get("item_ids")
    ]


async def candidates(
    user_id: str,
    items: list,
    context: dict,
    size: str | None = None,
    n: int | None = None,
    style_vector: list[float] | None = None,
) -> tuple[list[Outfit], str]:
    """(outfits, source) with source m02 or m02_mock."""
    cfg = get_config().m02
    n = n or cfg.n_candidates
    if cfg.source == "module":
        try:
            found = await _from_module(user_id, context, n, style_vector)
            known = {i.item_id for i in items}
            usable = [o for o in found if set(o.item_ids) <= known]
            if usable:
                return usable, "m02"
            if found:
                log.warning(
                    "M2 returned %d outfits, none with %s's M1 items (M2 demo wardrobe?): M5 mock used",
                    len(found),
                    user_id,
                )
        except Exception as e:  # M2 not ready / changed: keep M5 working
            log.warning("M2 unavailable, using the M5 mock of M2: %s", e)
    return mock_outfits(items, float(context.get("temp_c", 20)), size, n), "m02_mock"
