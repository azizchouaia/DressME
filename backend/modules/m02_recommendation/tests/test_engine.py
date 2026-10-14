"""Engine logic with stub models (no artifacts needed). Skipped where numpy / torch are not installed (CI)."""

import datetime as dt

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("torch")

from modules.m02_recommendation.engine.recommender import Ctx, Recommender, to_outfit  # noqa: E402
from modules.m02_recommendation.engine.wardrobe import Item  # noqa: E402

TODAY = dt.date(2026, 10, 14)


class StubAttributes:
    """Warmth / formality are stored in the first two dims of the fake embedding."""

    def __call__(self, emb, categories=None):
        return [
            {"warmth": float(e[0]), "formality": float(e[1]), "comfy": 0.5, "bold": 0.5, "classy": 0.5}
            for e in emb
        ]


class StubOutfitTransformer:
    """CP: outfits whose pieces have similar formality are 'compatible'. CIR: the ideal missing piece is the
    mean of the partial outfit, in the raw embedding space."""

    def compatibility(self, outfits):
        return np.array([1 - np.std(o[:, 1]) for o in outfits])

    def query(self, partials):
        return np.stack([p.mean(0) for p in partials])

    def item_space(self, vectors):
        return np.asarray(vectors)


def item(iid, cat, warmth=0.5, formality=0.5, **kw):
    e = np.zeros(8, np.float32)
    e[0], e[1], e[2] = warmth, formality, 1.0
    return Item(item_id=iid, category=cat, emb=e, **kw)


def wardrobe():
    return [
        item("t1", "top", 0.3, 0.2),
        item("t2", "top", 0.5, 0.8),
        item("t3", "top", 0.6, 0.5),
        item("b1", "bottom", 0.4, 0.2),
        item("b2", "bottom", 0.5, 0.8),
        item("b3", "bottom", 0.5, 0.5),
        item("d1", "dress", 0.3, 0.7),
        item("s1", "shoes", 0.3, 0.2),
        item("s2", "shoes", 0.5, 0.8),
        item("o1", "outerwear", 0.8, 0.6),
        item("o2", "outerwear", 0.7, 0.3),
    ]


def ctx(**kw):
    base = {
        "occasion": "work",
        "mood": None,
        "temp_c": 20.0,
        "condition": "clear",
        "rainy": False,
        "today": TODAY,
    }
    return Ctx(**{**base, **kw})


@pytest.fixture
def rec():
    return Recommender(StubOutfitTransformer(), StubAttributes())


def test_recommend_returns_complete_diverse_outfits(rec):
    c = ctx()
    items = rec.prepare(wardrobe(), c, set())
    out = rec.recommend(items, c, n=3)
    assert len(out) == 3
    for r in out:
        slots = [i.slot for i in r["items"]]
        assert "shoes" in slots
        assert ("dress" in slots) != ("top" in slots and "bottom" in slots)
    scores = [r["score"] for r in out]
    assert scores == sorted(scores, reverse=True)


def test_work_prefers_formal_pieces(rec):
    c = ctx(occasion="work")
    best = rec.recommend(rec.prepare(wardrobe(), c, set()), c, n=1)[0]
    assert np.mean([i.attrs["formality"] for i in best["items"]]) > 0.5


def test_cold_rain_requires_outerwear_and_heat_removes_it(rec):
    c = ctx(temp_c=9, condition="rain", rainy=True)
    for r in rec.recommend(rec.prepare(wardrobe(), c, set()), c, n=3):
        assert any(i.slot == "outerwear" for i in r["items"])
    c = ctx(temp_c=30)
    for r in rec.recommend(rec.prepare(wardrobe(), c, set()), c, n=3):
        assert not any(i.slot == "outerwear" for i in r["items"])


def test_laundry_and_excluded_pieces_never_suggested(rec):
    w = wardrobe()
    w[1].status = "laundry"
    c = ctx()
    items = rec.prepare(w, c, {"b2"})
    used = {i.item_id for r in rec.recommend(items, c, n=3) for i in r["items"]}
    assert "t2" not in used and "b2" not in used


def test_complete_keeps_pinned_pieces(rec):
    c = ctx()
    w = rec.prepare(wardrobe(), c, set())
    pinned = [i for i in w if i.item_id == "b1"]
    out = rec.complete([i for i in w if i.item_id != "b1"], c, pinned, n=3)
    assert out
    for r in out:
        ids = [i.item_id for i in r["items"]]
        assert "b1" in ids and not any(i.slot == "dress" for i in r["items"])


def test_swap_changes_only_one_slot(rec):
    c = ctx()
    w = rec.prepare(wardrobe(), c, set())
    by = {i.item_id: i for i in w}
    current = [by["t2"], by["b2"], by["s2"]]
    out = rec.swap(w, c, current, "top", n=5)
    assert out
    for r in out:
        ids = {i.item_id for i in r["items"]}
        assert {"b2", "s2"} <= ids and "t2" not in ids


def test_rotation_penalty_and_forgotten_bonus(rec):
    w = wardrobe()
    for i in w:
        i.last_worn = TODAY - dt.timedelta(days=10)
    w[1].last_worn = TODAY - dt.timedelta(days=1)  # t2 worn yesterday
    w[2].last_worn = TODAY - dt.timedelta(days=90)  # t3 forgotten
    c = ctx()
    items = rec.prepare(w, c, set())
    by = {i.item_id: i for i in items}
    b_recent = rec.breakdown([by["t2"], by["b2"], by["s2"]], 0.8, c)
    b_forgot = rec.breakdown([by["t3"], by["b2"], by["s2"]], 0.8, c)
    assert b_recent["rotation_penalty"] > 0.2
    assert b_forgot["forgotten_bonus"] > 0
    out = to_outfit({"items": [by["t3"], by["b2"], by["s2"]], "breakdown": b_forgot, "score": 0.7}, c, "u1")
    assert out["forgotten_item_id"] == "t3"
    assert any("not worn for 90 days" in r for r in out["reasons"])
