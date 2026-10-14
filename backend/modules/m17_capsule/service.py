"""Real implementation of M17 (same signatures as mock.py). Capsule wardrobe = combinatorial optimisation.

wardrobe ─► season filter (warmth read by M2)
         ─► 1. compatibility graph: every pair of pieces from different slots scored by M2 (pretrained
               OutfitTransformer); a piece's versatility = mean of its 5 best pairs -> keep the most
               versatile pieces per slot (candidate pool)
         ─► 2. candidate outfits from the pool (top+bottom+shoes, dress+shoes, + outerwear when the season
               asks) scored by M2 for each occasion: valid = compatibility >= threshold, weather fit and
               occasion fit >= 0.5
         ─► 3. integer linear programming (scipy / HiGHS): choose N pieces maximising the value of the valid
               outfits they complete, with category minimums and must-include pieces (greedy for comparison)
         ─► 4. 30-day plan: occasion of each day (M4 calendar), outfit that fits it, rotation
"""

from __future__ import annotations

import datetime as dt
import itertools
import time
from collections import Counter

import numpy as np

from .contract import SEASONS, CapsulePayload, PlanPayload

# a representative day of each season in Tunisia (temperature, condition) for the weather fit
SEASON_WEATHER = {
    "summer": (31.0, "clear"),
    "spring": (21.0, "clear"),
    "autumn": (18.0, "cloudy"),
    "winter": (11.0, "rain"),
}
OUTERWEAR = {"summer": "never", "spring": "optional", "autumn": "optional", "winter": "always"}
POOL = {"top": 12, "bottom": 8, "dress": 6, "shoes": 6, "outerwear": 4}
OUTER_PER_OUTFIT = 2  # outerwear variants tried per base outfit (the 2 that pair best with its top / dress)
SLOTS = ("top", "bottom", "dress", "shoes", "outerwear")
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _ok(result: dict) -> dict:
    return {"result": result, "mocked": False}


def season_of(day: dt.date) -> str:
    return {
        12: "winter",
        1: "winter",
        2: "winter",
        3: "spring",
        4: "spring",
        5: "spring",
        6: "summer",
        7: "summer",
        8: "summer",
        9: "summer",
        10: "autumn",
        11: "autumn",
    }[day.month]


def default_minimums(size: int, season: str) -> dict[str, int]:
    m = {
        "top": max(2, round(size * 0.3)),
        "bottom": max(2, round(size * 0.2)),
        "shoes": max(1, round(size * 0.12)),
    }
    if OUTERWEAR[season] == "always":
        m["outerwear"] = max(1, round(size * 0.1))
    return m


# ---------------- M2 / M4 (in-process, public API) ----------------
def _m2():
    from modules.m02_recommendation import router

    return router._impl()


def _wardrobe(user: str | None, items: list | None) -> list[dict]:
    """Pieces with category / name / image / attributes: inline (M1 format) or the M2 demo wardrobe."""
    if items is not None:
        return [
            {
                "item_id": g.item_id,
                "category": g.category.value,
                "name": g.subcategory or g.category.value,
                "image": g.image_cutout or g.image_raw,
                "attrs": {},
            }
            for g in items
        ]
    from modules.m02_recommendation import service as m2_service

    return m2_service.demo_wardrobe(user or "demo_f")["items"]


def _score(
    user: str | None, outfits: list[list[str]], occasion: str, season: str, items: list | None
) -> list[dict]:
    t, cond = SEASON_WEATHER[season]
    payload = {
        "context": {"occasion": occasion, "weather": {"temp_c": t, "condition": cond}},
        "options": {"rotation_window_days": 0, "forgotten_after_days": 0, "repeat_window_days": 0},
        "outfits": outfits,
    }
    if items is not None:
        payload["items"] = [g.model_dump(mode="json") for g in items]
    res = _m2().score({"user_id": user, "payload": payload})
    if res.get("mocked") or len(res["result"]["outfits"]) != len(outfits):
        raise ValueError("M2 did not score every outfit: M17 needs the real M2 (set M02_USE_MOCK=false)")
    return res["result"]["outfits"], res["result"].get("items", {})


def _day_occasions(user: str | None, start: dt.date, days: int) -> list[tuple[str, str]]:
    """(occasion, reason) per day: the M4 calendar when M4 runs, else weekdays work, weekend casual."""
    try:
        from modules.m04_scheduler import router as m4_router
        from modules.m04_scheduler import service as m4

        if m4_router._impl() is m4:
            cal = m4.calendar({"user_id": user, "payload": {"start": start.isoformat(), "days": days}})[
                "result"
            ]
            return [(d["occasion"], d["occasion_reason"]) for d in cal["days"]]
    except ImportError:
        pass
    return [
        (
            "work" if (start + dt.timedelta(k)).weekday() < 5 else "casual",
            WEEKDAYS[(start + dt.timedelta(k)).weekday()] + " default",
        )
        for k in range(days)
    ]


# ---------------- 1. compatibility graph ----------------
def _in_season(it: dict, season: str) -> bool:
    w = (it.get("attrs") or {}).get("warmth")
    if w is None or it["category"] not in SLOTS:
        return it["category"] in SLOTS
    if season == "summer":
        return it["category"] != "outerwear" and w <= 0.8
    if season == "winter":
        return it["category"] in ("outerwear", "shoes") or w >= 0.2
    return True


def _pairs(by: dict[str, list[str]], season: str) -> list[tuple[str, str]]:
    combos = [("top", "bottom"), ("top", "shoes"), ("bottom", "shoes"), ("dress", "shoes")]
    if OUTERWEAR[season] != "never":
        combos += [("top", "outerwear"), ("dress", "outerwear"), ("bottom", "outerwear")]
    return [(a, b) for ca, cb in combos for a in by.get(ca, []) for b in by.get(cb, [])]


def graph(user, wardrobe: list[dict], season: str, items_inline) -> tuple[dict, dict[str, float], dict]:
    by: dict[str, list[str]] = {}
    for it in wardrobe:
        by.setdefault(it["category"], []).append(it["item_id"])
    pairs = _pairs(by, season)
    scored, meta = (
        _score(user, [list(p) for p in pairs], "casual", season, items_inline) if pairs else ([], {})
    )
    edges = {}
    for p, o in zip(pairs, scored, strict=True):
        edges[frozenset(p)] = o["score_breakdown"]["compatibility"]
    best: dict[str, list[float]] = {}
    for p, c in edges.items():
        for i in p:
            best.setdefault(i, []).append(c)
    versatility = {i: float(np.mean(sorted(v, reverse=True)[:5])) for i, v in best.items()}
    return edges, versatility, meta


# ---------------- 2. candidate outfits ----------------
def candidates(by: dict[str, list[str]], edges: dict, season: str) -> list[tuple[str, ...]]:
    def outer_for(anchor: str) -> list[str]:
        outs = by.get("outerwear", [])
        return sorted(outs, key=lambda o: -edges.get(frozenset((anchor, o)), 0))[:OUTER_PER_OUTFIT]

    base = [tuple(o) for o in itertools.product(by.get("top", []), by.get("bottom", []), by.get("shoes", []))]
    base += [tuple(o) for o in itertools.product(by.get("dress", []), by.get("shoes", []))]
    mode = OUTERWEAR[season]
    out = []
    for o in base:
        if mode != "always":
            out.append(o)
        if mode != "never":
            out += [o + (x,) for x in outer_for(o[0])]
    return out


def score_outfits(user, outfits, occasions, season, items_inline, min_compat) -> list[dict]:
    """M2 scores each outfit for each occasion; keeps the valid ones with a value in [0, 1]."""
    per_occ = {
        occ: _score(user, [list(o) for o in outfits], occ, season, items_inline)[0] for occ in occasions
    }
    valid = []
    for k, o in enumerate(outfits):
        bds = {occ: per_occ[occ][k]["score_breakdown"] for occ in occasions}
        b0 = next(iter(bds.values()))
        fits = {occ: b["occasion_fit"] for occ, b in bds.items()}
        tags = [occ for occ, f in fits.items() if f >= 0.5]
        if b0["compatibility"] < min_compat or b0["weather_fit"] < 0.5 or not tags:
            continue
        value = 0.5 * b0["compatibility"] + 0.25 * b0["weather_fit"] + 0.25 * max(fits.values())
        valid.append(
            {
                "items": list(o),
                "value": round(value, 4),
                "occasions": tags,
                "compatibility": round(b0["compatibility"], 4),
                "weather_fit": round(b0["weather_fit"], 4),
                "occasion_fit": {k2: round(v, 3) for k2, v in fits.items()},
            }
        )
    return valid


# ---------------- 3. optimisation ----------------
def solve_ilp(
    items: list[str],
    cat: dict[str, str],
    outfits: list[dict],
    size: int,
    minimums: dict[str, int],
    must: list[str],
    coverage: dict[str, int] | None = None,
    time_limit: float = 20.0,
) -> tuple[list[str], dict]:
    """max sum(value_o * y_o)  s.t.  y_o <= x_i (i in o),  sum x = size,  sum_{i in c} x_i >= min_c,
    x_must = 1,
    sum_{o fits occasion k} y_o >= coverage_k,  x binary, 0 <= y <= 1.
    A tiny bonus per outfit makes ties prefer more outfits."""
    coverage = coverage or {}
    from scipy.optimize import Bounds, LinearConstraint, milp
    from scipy.sparse import lil_matrix

    n_i, n_o = len(items), len(outfits)
    idx = {i: k for k, i in enumerate(items)}
    c = np.concatenate([np.zeros(n_i), -np.array([o["value"] + 0.01 for o in outfits])])
    rows = sum(len(o["items"]) for o in outfits)
    a = lil_matrix((rows + 1 + len(minimums) + len(coverage), n_i + n_o))
    lo, hi = [], []
    r = 0
    for j, o in enumerate(outfits):  # y_o - x_i <= 0
        for i in o["items"]:
            a[r, n_i + j], a[r, idx[i]] = 1, -1
            lo.append(-np.inf)
            hi.append(0)
            r += 1
    a[r, :n_i] = 1  # capsule size
    lo.append(size)
    hi.append(size)
    r += 1
    for cname, m in minimums.items():
        for i in items:
            if cat[i] == cname:
                a[r, idx[i]] = 1
        lo.append(m)
        hi.append(np.inf)
        r += 1
    for occ, k in coverage.items():  # enough outfits for every occasion
        for j, o in enumerate(outfits):
            if occ in o["occasions"]:
                a[r, n_i + j] = 1
        lo.append(k)
        hi.append(np.inf)
        r += 1
    lb = np.zeros(n_i + n_o)
    for i in must:
        if i in idx:
            lb[idx[i]] = 1
    t0 = time.time()
    res = milp(
        c,
        constraints=LinearConstraint(a.tocsr(), lo, hi),
        bounds=Bounds(lb, np.ones(n_i + n_o)),
        integrality=np.concatenate([np.ones(n_i), np.zeros(n_o)]),
        options={"time_limit": time_limit, "mip_rel_gap": 0.005},
    )
    if res.x is None:
        raise ValueError(f"no capsule satisfies the constraints ({res.message})")
    chosen = [items[k] for k in range(n_i) if res.x[k] > 0.5]
    return chosen, {
        "method": "ilp",
        "solver": "HiGHS (scipy.optimize.milp)",
        "status": res.message,
        "optimal": bool(res.status == 0),
        "seconds": round(time.time() - t0, 2),
    }


def solve_greedy(
    items: list[str],
    cat: dict[str, str],
    outfits: list[dict],
    size: int,
    minimums: dict[str, int],
    must: list[str],
    coverage: dict[str, int] | None = None,
) -> tuple[list[str], dict]:
    """Add the piece with the best gain (completed outfits, plus half credit for outfits it brings one piece
    away from completion), while keeping room for the category minimums."""
    t0 = time.time()
    chosen = [i for i in must if i in cat]
    sets = [(set(o["items"]), o["value"] + 0.01) for o in outfits]

    occs = [o["occasions"] for o in outfits]
    coverage = coverage or {}

    def value(sel: set[str]) -> float:
        done = [k for k, (s, _) in enumerate(sets) if s <= sel]
        near = sum(v for s, v in sets if len(s - sel) == 1)
        covered = sum(min(sum(occ in occs[k] for k in done), n) for occ, n in coverage.items())
        return sum(sets[k][1] for k in done) + 2.0 * covered + 0.5 * near / max(1, len(sel))

    while len(chosen) < size:
        have = Counter(cat[i] for i in chosen)
        missing = {c: m - have[c] for c, m in minimums.items() if m > have[c]}
        free = size - len(chosen)
        pool = [i for i in items if i not in chosen]
        if sum(missing.values()) >= free:  # only pieces of missing categories now
            pool = [i for i in pool if cat[i] in missing]
        if not pool:
            break
        sel = set(chosen)
        best = max(pool, key=lambda i: value(sel | {i}))
        chosen.append(best)
    return chosen, {"method": "greedy", "seconds": round(time.time() - t0, 2)}


# ---------------- 4. plan ----------------
def plan(outfits: list[dict], days: list[tuple[str, str]], start: dt.date) -> list[dict]:
    """Each day: an outfit for its occasion, high value, not worn in the last 7 days, new pieces."""
    last_used: dict[int, int] = {}
    uses = Counter()
    out = []
    prev: set[str] = set()
    for k, (occ, why) in enumerate(days):
        pool = [j for j, o in enumerate(outfits) if occ in o["occasions"]] or list(range(len(outfits)))
        if not pool:
            out.append(
                {
                    "date": (start + dt.timedelta(k)).isoformat(),
                    "occasion": occ,
                    "reason": why,
                    "outfit": None,
                }
            )
            continue

        def cost(j: int, k: int = k, prev: set[str] = prev) -> float:
            o = outfits[j]
            recent = k - last_used.get(j, -99) < 7
            return -o["value"] + 0.6 * recent + 0.15 * len(prev & set(o["items"])) + 0.05 * uses[j]

        j = min(pool, key=cost)
        last_used[j], prev = k, set(outfits[j]["items"])
        uses[j] += 1
        d = start + dt.timedelta(k)
        out.append(
            {
                "date": d.isoformat(),
                "weekday": WEEKDAYS[d.weekday()],
                "occasion": occ,
                "reason": why,
                "outfit": outfits[j],
            }
        )
    return out


# ---------------- endpoints ----------------
def _build(
    user, wardrobe, meta, edges, chosen, outfits_all, season, occasions, plan_days, start, extra
) -> dict:
    sel = set(chosen)
    outs = sorted([o for o in outfits_all if set(o["items"]) <= sel], key=lambda o: -o["value"])
    uses = Counter(i for o in outs for i in o["items"])
    info = {it["item_id"]: it for it in wardrobe}
    info.update({k: {**info.get(k, {}), **v} for k, v in meta.items()})
    pieces = [
        {
            "item_id": i,
            "name": info.get(i, {}).get("name", i),
            "category": info.get(i, {}).get("category"),
            "image": info.get(i, {}).get("image"),
            "outfits": uses[i],
        }
        for i in chosen
    ]
    order = list(SLOTS) + ["accessory"]
    pieces.sort(key=lambda p: (order.index(p["category"]) if p["category"] in order else 9, -p["outfits"]))
    top_edges = sorted(((sorted(p), round(c, 3)) for p, c in edges.items() if p <= sel), key=lambda e: -e[1])[
        :30
    ]
    result = {
        "season": season,
        "occasions": occasions,
        "size": len(chosen),
        "pieces": pieces,
        "outfits": outs,
        "n_outfits": len(outs),
        "by_occasion": {occ: sum(occ in o["occasions"] for o in outs) for occ in occasions},
        "unused_pieces": [i for i in chosen if uses[i] == 0],
        "graph_edges": [{"items": e, "compatibility": c} for e, c in top_edges],
        "items": {i: {k: info.get(i, {}).get(k) for k in ("name", "category", "image")} for i in sel},
        **extra,
    }
    if plan_days:
        st = start or dt.date.today()
        result["plan"] = plan(outs, _day_occasions(user, st, plan_days), st)
        worn = Counter(tuple(d["outfit"]["items"]) for d in result["plan"] if d["outfit"])
        result["plan_stats"] = {
            "days": plan_days,
            "different_outfits": len(worn),
            "max_repeats": max(worn.values()) if worn else 0,
        }
    return result


def capsule(req: dict) -> dict:
    p = CapsulePayload.model_validate(req.get("payload") or {})
    user = req.get("user_id")
    t0 = time.time()
    season = season_of(p.start or dt.date.today()) if p.season == "auto" else p.season
    if season not in SEASONS[1:]:
        raise ValueError("season must be auto / spring / summer / autumn / winter")
    wardrobe = [it for it in _wardrobe(user, p.items) if it["item_id"] not in set(p.exclude_item_ids)]
    wardrobe = [it for it in wardrobe if _in_season(it, season) or it["item_id"] in p.must_include]
    edges, versatility, meta = graph(user, wardrobe, season, p.items)
    cat = {it["item_id"]: it["category"] for it in wardrobe}
    by: dict[str, list[str]] = {}
    for c in SLOTS:
        ids = sorted([i for i in cat if cat[i] == c], key=lambda i: -versatility.get(i, 0))
        keep = ids[: POOL[c]] + [i for i in ids[POOL[c] :] if i in p.must_include]
        if keep:
            by[c] = keep
    cands = candidates(by, edges, season)
    valid = score_outfits(user, cands, p.occasions, season, p.items, p.min_compatibility)
    pool = [i for c in by.values() for i in c]
    minimums = p.minimums or default_minimums(p.size, season)
    minimums = {c: m for c, m in minimums.items() if m > 0}
    for c, m in minimums.items():
        if len(by.get(c, [])) < m:
            raise ValueError(f"not enough {c} pieces in season for the minimum {m}")
    size = min(p.size, len(pool))
    # every occasion gets at least a fair share of outfits (lowered if the wardrobe cannot do it)
    target = max(2, size // (2 * len(p.occasions)))
    coverage = {occ: min(target, sum(occ in o["occasions"] for o in valid)) for occ in p.occasions}
    runs = {}
    if p.method in ("ilp", "both"):
        try:
            runs["ilp"] = solve_ilp(pool, cat, valid, size, minimums, p.must_include, coverage)
        except ValueError:  # coverage impossible with these minimums: best effort without it
            runs["ilp"] = solve_ilp(pool, cat, valid, size, minimums, p.must_include)
    if p.method in ("greedy", "both"):
        runs["greedy"] = solve_greedy(pool, cat, valid, size, minimums, p.must_include, coverage)
    if not runs:
        raise ValueError("method must be ilp / greedy / both")
    comparison = {}
    for name, (chosen, info) in runs.items():
        sel = set(chosen)
        done = [o for o in valid if set(o["items"]) <= sel]
        comparison[name] = {**info, "n_outfits": len(done), "value": round(sum(o["value"] for o in done), 3)}
    best = max(runs, key=lambda k: comparison[k]["value"])
    extra = {
        "method": best,
        "comparison": comparison,
        "minimums": minimums,
        "coverage_target": coverage,
        "wardrobe": {
            "pieces": len(wardrobe),
            "candidate_pool": len(pool),
            "candidate_outfits": len(cands),
            "valid_outfits": len(valid),
        },
        "seconds": round(time.time() - t0, 1),
    }
    return _ok(
        _build(
            user,
            wardrobe,
            meta,
            edges,
            runs[best][0],
            valid,
            season,
            p.occasions,
            p.plan_days,
            p.start,
            extra,
        )
    )


def plan_capsule(req: dict) -> dict:
    """Outfits + plan for a capsule the user already has (its piece ids)."""
    p = PlanPayload.model_validate(req.get("payload") or {})
    user = req.get("user_id")
    season = season_of(p.start or dt.date.today()) if p.season == "auto" else p.season
    sel = set(p.item_ids)
    wardrobe = [it for it in _wardrobe(user, p.items) if it["item_id"] in sel]
    edges, _, meta = graph(user, wardrobe, season, p.items)
    by: dict[str, list[str]] = {}
    for it in wardrobe:
        by.setdefault(it["category"], []).append(it["item_id"])
    valid = score_outfits(
        user, candidates(by, edges, season), p.occasions, season, p.items, p.min_compatibility
    )
    return _ok(
        _build(
            user,
            wardrobe,
            meta,
            edges,
            [it["item_id"] for it in wardrobe],
            valid,
            season,
            p.occasions,
            p.plan_days,
            p.start,
            {"method": "given"},
        )
    )
