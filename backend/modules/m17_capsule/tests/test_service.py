"""Capsule optimisation with a deterministic fake M2 scorer (no models needed)."""

import datetime as dt
import itertools

import pytest

pytest.importorskip("scipy")

from modules.m17_capsule import service  # noqa: E402

CATS = {"t": "top", "b": "bottom", "s": "shoes", "o": "outerwear", "d": "dress"}
# id = <category letter><n>; formal pieces end with "f"
IDS = [
    "t1",
    "t2",
    "t3",
    "t4f",
    "t5f",
    "t6",
    "b1",
    "b2",
    "b3f",
    "b4",
    "s1",
    "s2f",
    "s3",
    "o1",
    "o2",
    "d1f",
    "d2",
]


def items():
    from modules.m02_recommendation.contract import WardrobeItem

    return [
        WardrobeItem(item_id=i, user_id="u1", image_raw="", category=CATS[i[0]], subcategory=CATS[i[0]])
        for i in IDS
    ]


def fake_score(user, outfits, occasion, season, items_inline):
    """Compatibility from a fixed hash of the pieces; work fits outfits whose top/bottom/dress are formal."""
    out = []
    for o in outfits:
        h = sum((k + 1) * (ord(c) % 7) for k, c in enumerate("".join(sorted(o)))) % 100
        formal = all(i.endswith("f") for i in o if i[0] in "tbd")
        fit = (0.9 if formal else 0.2) if occasion == "work" else (0.3 if formal else 0.9)
        out.append(
            {"score_breakdown": {"compatibility": 0.4 + h / 160, "weather_fit": 0.9, "occasion_fit": fit}}
        )
    return out, {}


@pytest.fixture(autouse=True)
def stub(monkeypatch):
    monkeypatch.setattr(service, "_score", fake_score)
    monkeypatch.setattr(
        service,
        "_day_occasions",
        lambda user, start, days: [
            ("work" if (start + dt.timedelta(k)).weekday() < 5 else "casual", "default") for k in range(days)
        ],
    )


def run(**payload):
    payload.setdefault("items", [i.model_dump(mode="json") for i in items()])
    payload.setdefault("season", "autumn")
    payload.setdefault("min_compatibility", 0.5)
    return service.capsule({"user_id": "u1", "payload": payload})["result"]


def test_size_minimums_must_include():
    r = run(size=8, minimums={"top": 3, "bottom": 2, "shoes": 2}, must_include=["o2"], plan_days=0)
    ids = [p["item_id"] for p in r["pieces"]]
    cats = [p["category"] for p in r["pieces"]]
    assert len(ids) == 8 and "o2" in ids
    assert cats.count("top") >= 3 and cats.count("bottom") >= 2 and cats.count("shoes") >= 2
    assert all(set(o["items"]) <= set(ids) for o in r["outfits"])
    assert r["n_outfits"] == len(r["outfits"]) > 0


def test_ilp_is_optimal_and_beats_or_ties_greedy():
    r = run(
        size=6, minimums={"top": 2, "bottom": 1, "shoes": 1}, method="both", plan_days=0, occasions=["casual"]
    )
    ilp, greedy = r["comparison"]["ilp"], r["comparison"]["greedy"]
    assert ilp["optimal"] and ilp["value"] >= greedy["value"]
    # brute force on the same valid outfits: no 6-piece set does better
    pool = [i for i in IDS if i[0] in "tbsdo"]
    edges, vers, _ = service.graph(
        "u1", [{"item_id": i, "category": CATS[i[0]], "attrs": {}} for i in pool], "autumn", None
    )
    by = {}
    for i in pool:
        by.setdefault(CATS[i[0]], []).append(i)
    valid = service.score_outfits(
        "u1", service.candidates(by, edges, "autumn"), ["casual"], "autumn", None, 0.5
    )
    best = 0.0
    for combo in itertools.combinations(pool, 6):
        s = set(combo)
        cats = [CATS[i[0]] for i in combo]
        if cats.count("top") < 2 or cats.count("bottom") < 1 or cats.count("shoes") < 1:
            continue
        best = max(best, sum(o["value"] + 0.01 for o in valid if set(o["items"]) <= s))
    assert ilp["value"] + 0.01 * ilp["n_outfits"] == pytest.approx(best, abs=1e-6)


def test_every_occasion_is_covered():
    r = run(size=10, occasions=["casual", "work"], plan_days=0)
    assert r["by_occasion"]["work"] >= r["coverage_target"]["work"] > 0
    assert r["by_occasion"]["casual"] >= r["coverage_target"]["casual"]


def test_plan_matches_occasions_and_rotates():
    r = run(size=12, plan_days=28, start="2026-10-12")  # a Monday
    plan = r["plan"]
    assert len(plan) == 28
    for d in plan:
        assert d["occasion"] in d["outfit"]["occasions"] or not any(
            d["occasion"] in o["occasions"] for o in r["outfits"]
        )
    # the same outfit never comes back within 7 days when there are enough outfits for that occasion
    for occ in ("work", "casual"):
        n = sum(occ in o["occasions"] for o in r["outfits"])
        days = [k for k, d in enumerate(plan) if d["occasion"] == occ]
        if n >= 7:
            for a, b in itertools.combinations(days, 2):
                if b - a < 7:
                    assert plan[a]["outfit"]["items"] != plan[b]["outfit"]["items"]


def test_season_rules():
    assert (
        service.season_of(dt.date(2026, 7, 1)) == "summer"
        and service.season_of(dt.date(2026, 1, 5)) == "winter"
    )
    by = {"top": ["t1"], "bottom": ["b1"], "shoes": ["s1"], "outerwear": ["o1"], "dress": []}
    assert all(len(o) == 3 for o in service.candidates(by, {}, "summer"))  # no jacket in summer
    assert all(len(o) == 4 for o in service.candidates(by, {}, "winter"))  # always a jacket in winter
    assert service.default_minimums(12, "winter")["outerwear"] >= 1


def test_impossible_minimums_is_a_clear_error():
    with pytest.raises(ValueError):
        run(size=8, minimums={"dress": 5}, plan_days=0)
