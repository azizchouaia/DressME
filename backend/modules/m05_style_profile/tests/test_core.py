"""Pure logic of M5: style mix, features, Linear TS, prior, attributes, M2 mock, simulation."""

import datetime as dt
import random
from types import SimpleNamespace

import numpy as np
import pytest

from modules.m05_style_profile import m02_client, m03_client, prior, rocchio
from modules.m05_style_profile.attributes import warmth
from modules.m05_style_profile.bandit import LinearTS
from modules.m05_style_profile.config import load_reference_looks, load_styles
from modules.m05_style_profile.features import Layout
from modules.m05_style_profile.styles import StyleSpace, style_mix
from shared.schemas import Color

STYLES = load_styles()


def layout(cfg, styles=None) -> Layout:
    return Layout.build(styles or STYLES.ids, cfg.context)


def space_with(vectors: np.ndarray, factor=30.0) -> StyleSpace:
    return StyleSpace(STYLES, vectors / np.linalg.norm(vectors, axis=1, keepdims=True), factor)


def item(
    item_id,
    category="top",
    subcategory="shirt",
    season=("spring",),
    material="cotton",
    formality=0.5,
    colors=(("navy", 1.0),),
    price=None,
    size=None,
    status="active",
    last_worn=None,
    wear_count=0,
):
    return SimpleNamespace(
        item_id=item_id,
        category=category,
        subcategory=subcategory,
        season=list(season),
        material=material,
        formality=formality,
        size=size,
        status=status,
        price_tnd=price,
        colors=[Color(name=c, hex="#000000", share=s) for c, s in colors],
        last_worn=last_worn,
        wear_count=wear_count,
        image_raw="r",
        image_cutout=None,
    )


# ---------- style list + style mix ----------


def test_style_list_has_12_styles_in_9_families():
    assert len(STYLES.ids) == 12 and len(STYLES.families) == 9
    assert {s.family for s in STYLES.styles} == set(STYLES.families)
    assert STYLES.family_of("classic") == "elegant" and STYLES.family_of("vintage") == "romantic"
    assert len(STYLES.version) == 12


def test_reference_looks_cover_every_style_and_one_primary_per_family():
    looks = load_reference_looks()
    assert {lk.style_id for lk in looks} == set(STYLES.ids)
    primary = [STYLES.family_of(lk.style_id) for lk in looks if lk.primary]
    assert sorted(primary) == sorted(STYLES.families)  # the swipe cards show one look per family


def test_style_mix_sums_to_one_and_picks_the_closest_style():
    rng = np.random.default_rng(0)
    styles = rng.standard_normal((12, 512))
    item_vec = styles[6] + 0.3 * rng.standard_normal(512)  # close to style 6
    mix = style_mix(item_vec, styles, factor=30)
    assert mix.shape == (12,) and abs(mix.sum() - 1) < 1e-9 and int(np.argmax(mix)) == 6
    batch = style_mix(np.stack([item_vec, styles[2]]), styles)
    np.testing.assert_allclose(batch[0], mix)
    assert int(np.argmax(batch[1])) == 2


def test_style_mix_factor_is_a_temperature():
    rng = np.random.default_rng(1)
    styles, item_vec = rng.standard_normal((12, 512)), rng.standard_normal(512)
    assert style_mix(item_vec, styles, 100).max() > style_mix(item_vec, styles, 5).max()


def test_space_helpers():
    space = space_with(np.eye(12, 512))
    mix = space.as_dict(space.mix(np.eye(12, 512)[STYLES.ids.index("classic")]))
    assert max(mix, key=mix.get) == "classic"
    fam = space.families({"classic": 0.5, "minimalist": 0.2, "casual": 0.3})
    assert list(fam)[0] == "elegant" and fam["elegant"] == pytest.approx(0.7)
    assert space.top({"classic": 0.5, "casual": 0.3}, 1) == [
        {"style": "classic", "family": "elegant", "share": 0.5}
    ]


# ---------- features ----------


def test_dimension_follows_the_style_list(cfg):
    assert layout(cfg).dim == 90  # 1 + 16 + 6*12 + 1
    assert layout(cfg).C == 6
    for s in (5, 12, 40, 60):
        assert layout(cfg, [f"s{i}" for i in range(s)]).dim == 1 + (s + 4) + 6 * s + 1


def test_context_vector_and_baseline_occasion(cfg):
    lay = layout(cfg)
    np.testing.assert_allclose(lay.context_vector(30, True, False, "work"), [1, 1, 1, 0, 0, 0])
    np.testing.assert_allclose(lay.context_vector(0, False, True, "sport"), [-1, 0, 0, 0, 0, 1])
    np.testing.assert_allclose(lay.context_vector(60, False, False, "event")[0], 1.0)  # clipped


def test_features_layout_and_indices(cfg):
    lay = layout(cfg)
    mix = np.zeros(12)
    mix[STYLES.ids.index("classic")] = 1
    ctx = lay.context_vector(30, False, False, "work")
    x = lay.features(ctx, lay.outfit_vector(mix, 0.8, 0.6, 0.5, 0.3))
    assert x.shape == (90,) and x[0] == 1
    assert x[lay.style_index("classic")] == 1 and x[lay.formality_index] == 0.8
    assert x[lay.warmth_index] == 0.6 and x[lay.novelty_index] == 0.5 and x[lay.taste_index] == 0.3
    assert x[lay.interaction_index("occ_work", "classic")] == 1
    assert x[lay.interaction_index("occ_casual", "classic")] == 0
    assert x[lay.temp_warmth_index] == pytest.approx(0.6)
    with pytest.raises(ValueError):
        lay.outfit_vector(np.zeros(5), 0, 0, 0, 0)


def test_feature_names_are_readable(cfg):
    lay = layout(cfg)
    assert lay.describe(lay.interaction_index("occ_work", "classic"), 0.4)[1] == "likes classic for work"
    assert "avoids warm outfits when it's hot" in lay.describe(lay.temp_warmth_index, -0.3)[1]
    assert (
        lay.describe(lay.style_index("bohemian"), -0.2, {"bohemian": "Bohemian"})[1]
        == "avoids Bohemian outfits"
    )
    keys = {lay.describe(i, 1.0)[0] for i in range(lay.dim)}
    assert len(keys) == lay.dim  # every feature has its own name


# ---------- Linear TS ----------


def test_linear_ts_init_from_prior():
    p = np.arange(5, dtype=float)
    m = LinearTS(5, p, prior_strength=2.0, v=0.3)
    np.testing.assert_allclose(m.A, 2 * np.eye(5))
    np.testing.assert_allclose(m.b, 2 * p)
    np.testing.assert_allclose(m.mean, p)
    with pytest.raises(ValueError):
        LinearTS(5, np.zeros(4))


def test_linear_ts_choose_rank_update_shapes():
    rng = np.random.default_rng(0)
    m = LinearTS(8, v=0.3)
    X = rng.standard_normal((20, 8))
    order, scores = m.choose(X, k=10, rng=rng)
    assert order.shape == (10,) and scores.shape == (20,) and len(set(order)) == 10
    assert list(order) == list(np.argsort(-scores)[:10])
    r_order, _ = m.rank(X)
    assert r_order.shape == (20,)
    m.update(X[0], 1.0, weight=0.5)
    np.testing.assert_allclose(m.A, np.eye(8) + 0.5 * np.outer(X[0], X[0]))
    np.testing.assert_allclose(m.b, 0.5 * X[0])
    assert m.n_updates == 1


def test_linear_ts_learns_a_linear_reward():
    rng = np.random.default_rng(3)
    theta = np.array([0.5, -1.0, 2.0, 0.0])
    m = LinearTS(4, v=0.3)
    for _ in range(400):
        x = rng.standard_normal(4)
        m.update(x, float(x @ theta + 0.05 * rng.standard_normal()))
    np.testing.assert_allclose(m.mean, theta, atol=0.05)
    assert m.std().max() < 0.05


def test_thompson_sample_has_the_posterior_covariance():
    rng = np.random.default_rng(0)
    m = LinearTS(3, v=0.5)
    m.update([1, 0, 0], 1.0)
    m.update([1, 0, 0], 1.0)  # A = diag(3, 1, 1)
    draws = np.array([m.sample_theta(rng) for _ in range(20000)])
    np.testing.assert_allclose(draws.std(axis=0), 0.5 / np.sqrt([3, 1, 1]), rtol=0.05)
    np.testing.assert_allclose(m.std(), 0.5 / np.sqrt([3, 1, 1]))


def test_linear_ts_serialisation_round_trip():
    rng = np.random.default_rng(1)
    m = LinearTS(6, rng.standard_normal(6), prior_strength=2.0, v=0.2)
    for _ in range(5):
        m.update(rng.standard_normal(6), rng.random(), weight=0.5)
    for back in (
        LinearTS.from_dict(m.to_dict()),
        LinearTS.from_bytes(6, *m.to_bytes(), m.prior_strength, m.v, m.n_updates),
    ):
        np.testing.assert_array_equal(back.A, m.A)
        np.testing.assert_array_equal(back.b, m.b)
        np.testing.assert_array_equal(back.prior_mean, m.prior_mean)
        assert (back.v, back.prior_strength, back.n_updates) == (0.2, 2.0, 5)


def test_shift_prior_keeps_the_learning():
    rng = np.random.default_rng(2)
    xs = [rng.standard_normal(4) for _ in range(6)]
    old, new = np.zeros(4), np.array([0.3, 0, 0, 0.5])
    shifted = LinearTS(4, old, prior_strength=2.0)
    fresh = LinearTS(4, new, prior_strength=2.0)
    for x in xs:
        shifted.update(x, 1.0)
        fresh.update(x, 1.0)
    shifted.shift_prior(new)
    np.testing.assert_allclose(shifted.b, fresh.b)
    np.testing.assert_allclose(shifted.mean, fresh.mean)


# ---------- prior + taste ----------


def test_prior_is_neutral_then_follows_the_wishes(cfg):
    lay = layout(cfg)
    neutral = prior.build_prior(lay, {}, cfg)  # a new user: no question asked
    assert neutral.shape == (lay.dim,) and neutral[lay.taste_index] == pytest.approx(0.5)
    assert np.count_nonzero(neutral) == 1
    p = prior.build_prior(lay, {"want_more": ["classic"], "want_less": ["streetwear", "unknown"]}, cfg)
    assert p[lay.style_index("classic")] == pytest.approx(0.2)
    assert p[lay.style_index("streetwear")] == pytest.approx(-0.3)
    assert np.count_nonzero(p) == 3


def test_rocchio_taste(cfg):
    e = np.eye(4, 512)
    assert rocchio.taste(None, 0, None, 0, cfg=cfg) is None  # nothing liked yet
    liked, n = rocchio.accumulate(None, 0, e[0], 1.0)
    liked, n = rocchio.accumulate(liked, n, e[1], 1.0)
    rejected, m = rocchio.accumulate(None, 0, e[2], 0.5)  # source weight 0.5 (chat)
    t = rocchio.taste(liked, n, rejected, m, cfg=cfg)
    expected = np.array([0.5, 0.5, -0.3]) / np.linalg.norm([0.5, 0.5, -0.3])
    np.testing.assert_allclose(t[:3], expected)
    assert t[3] == 0
    t = rocchio.taste(liked, n, rejected, m, more=[e[3]], less=[e[0]], cfg=cfg)
    assert t[3] > 0 and t[0] < t[1]
    assert rocchio.taste(None, 0, None, 0, more=[e[3]], cfg=cfg)[3] == pytest.approx(1.0)  # a wish alone


def test_rocchio_pick_keeps_discovery_cards():
    sims = np.linspace(1, 0, 20)  # candidate i has similarity 1 - i/19
    picks = rocchio.pick(sims, 10, 2, random.Random(0))
    exploit = [i for i, e in picks if not e]
    explore = [i for i, e in picks if e]
    assert exploit == list(range(8)) and len(explore) == 2 and all(i >= 14 for i in explore)
    assert [i for i, _ in rocchio.pick(sims[:5], 10, 2, random.Random(0))].count(0) == 1
    assert sorted(i for i, _ in rocchio.pick(sims[:5], 10, 2, random.Random(0))) == [0, 1, 2, 3, 4]
    assert rocchio.pick(sims[:1], 10, 2, random.Random(0)) == [(0, False)]


# ---------- attributes ----------


def test_warmth_from_seasons_and_bonuses():
    assert warmth(item("a", season=["summer"])) == 0.0
    assert warmth(item("a", season=["winter"], subcategory="coat", material="wool")) == 1.0
    assert warmth(item("a", season=["spring", "autumn"])) == pytest.approx(0.5)
    assert warmth(item("a", season=[])) == 0.5
    assert warmth(item("a", season=["summer"], material="linen")) == 0.0  # clipped


# ---------- mocks of M2 / M3 ----------


def wardrobe():
    return [
        item("t1"),
        item("t2", season=["winter"], subcategory="sweater", material="wool", size="L"),
        item("b1", category="bottom", subcategory="jeans"),
        item("b2", category="bottom", season=["summer"]),
        item("d1", category="dress", season=["summer"]),
        item("s1", category="shoes"),
        item("o1", category="outerwear", season=["winter"], subcategory="coat"),
        item("x1", category="bottom", status="archived"),
    ]


def test_m02_mock_builds_valid_outfits():
    outfits = m02_client.mock_outfits(wardrobe(), temp_c=20, rng=random.Random(0))
    assert outfits and len({o.outfit_id for o in outfits}) == len(outfits)
    for o in outfits:
        assert "x1" not in o.item_ids  # not available
        assert ("d1" in o.item_ids) != any(i.startswith("t") for i in o.item_ids)  # top+bottom or a dress
        assert o.score_breakdown.keys() == {"compatibility", "weather_fit"}
        assert o.outfit_id == m02_client.outfit_id_for(o.item_ids)


def test_m02_mock_filters_heat_and_size():
    hot = m02_client.mock_outfits(wardrobe(), temp_c=32, rng=random.Random(0))
    assert hot and all(i not in o.item_ids for o in hot for i in ("t2", "o1"))
    sized = m02_client.mock_outfits(wardrobe(), temp_c=10, size="M", rng=random.Random(0))
    assert all("t2" not in o.item_ids for o in sized)  # size L
    cold = m02_client.mock_outfits(wardrobe(), temp_c=5, n=40, rng=random.Random(1))
    assert any("o1" in o.item_ids for o in cold)
    assert m02_client.mock_outfits([item("s1", category="shoes")], 20) == []


class FakeM2:
    """modules.m02_recommendation's impl: records the payload, answers the given outfits."""

    def __init__(self, outfits):
        self.outfits, self.payloads = outfits, []

    def recommend(self, req: dict) -> dict:
        self.payloads.append(req["payload"])
        return {"result": {"outfits": self.outfits}, "mocked": False}


async def test_m02_module_gets_the_taste_and_must_use_the_users_items(cfg, monkeypatch):
    from modules.m02_recommendation import router as m02_router

    monkeypatch.setattr(cfg.m02, "source", "module")
    items = wardrobe()
    fake = FakeM2([{"outfit_id": "o1", "items": ["t1", "b1", "s1"]}, {"outfit_id": "o2", "items": ["demo"]}])
    monkeypatch.setattr(m02_router, "_impl", lambda: fake)
    context = {"occasion": "uni", "temp_c": 12}
    outfits, source = await m02_client.candidates("u1", items, context, style_vector=[0.1, 0.2])
    assert source == "m02" and [o.outfit_id for o in outfits] == ["o1"]  # o2: not the user's pieces
    sent = fake.payloads[0]
    assert sent["options"]["style_vector"] == [0.1, 0.2] and sent["context"]["occasion"] == "casual"  # uni
    fake.outfits = [{"outfit_id": "o3", "items": ["demo_a", "demo_b"]}]  # M2 on its demo wardrobe
    outfits, source = await m02_client.candidates("u1", items, {"temp_c": 12})
    assert source == "m02_mock" and outfits and "style_vector" not in fake.payloads[1]["options"]


def test_m03_mock_and_item_fields(cfg, monkeypatch):
    pieces = [item("a", last_worn=dt.date(2026, 10, 1)), item("b")]
    assert m03_client.novelty(pieces) == 0.5
    monkeypatch.setattr(cfg.m03, "source", "item_fields")
    assert m03_client.novelty(pieces, dt.date(2026, 10, 16)) == pytest.approx(0.5)
    assert m03_client.novelty([item("b")], dt.date(2026, 10, 16)) == 1.0


# ---------- simulation ----------


def test_simulation_bandit_beats_random():
    from modules.m05_style_profile.scripts.simulate import simulate

    bandit, rand = [], []
    for seed in range(6):
        b, r = simulate(days=300, seed=seed, verbose=False)
        bandit += b[100:]
        rand += r[100:]
    assert np.mean(bandit) > np.mean(rand) + 0.05
