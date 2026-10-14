import pytest

from modules.m06_smartbuy.agent import SmartBuyAgent
from modules.m06_smartbuy.pipeline import gap, score


@pytest.fixture(scope="module")
def agent():
    # these tests check the hand-made RULES behaviour on the tiny demo set
    from modules.m06_smartbuy.agent import CONFIG
    return SmartBuyAgent({**CONFIG, "decision": "rules", "personalize": False})


async def run(agent, img, price=80, **kw):
    return await agent({"user_id": "usr_demo", "probe_image": img, "price_tnd": price, **kw})


async def test_duplicate_is_skipped(agent):
    out = await run(agent, "cand_navy_shirt")
    assert out["is_duplicate"] and out["verdict"] == "skip"
    assert out["buy_links"] == []


async def test_versatile_gap_piece_is_bought(agent):
    out = await run(agent, "cand_white_shirt", 79)
    assert out["verdict"] == "buy"
    assert out["fills_gap"] == "white shirt"
    assert out["new_outfits"] >= 4


async def test_piece_matching_nothing_is_skipped(agent):
    out = await run(agent, "cand_red_dress", 180)
    assert out["verdict"] == "skip"


async def test_size_advice(agent):
    out = await run(agent, "cand_white_shirt", 79, shop_brand="Medina Atelier", body={"chest_cm": 98})
    assert out["size_advice"]["size"] == "M"


def test_thresholds():
    cfg = {"buy_threshold": 70, "skip_threshold": 40}
    assert score.verdict(80, False, cfg) == "buy"
    assert score.verdict(55, False, cfg) == "think"
    assert score.verdict(90, True, cfg) == "skip"
    assert score.verdict(90, False, {**cfg, "max_same_type": 3}, 3) == "think"


def test_gap_matching():
    assert gap.fill(["white shirt", "light jacket"], "shirt", "white") == "white shirt"
    assert gap.fill(["white shirt"], "shirt", "navy") is None


async def test_same_type_other_colour_is_not_duplicate(agent):
    out = await run(agent, "cand_grey_jeans", 95)
    assert not out["is_duplicate"] and out["verdict"] == "think"


async def test_too_many_same_type_caps_at_think(agent):
    out = await run(agent, "cand_olive_tee", 25)
    assert out["verdict"] == "think"
    assert any("t-shirts" in r for r in out["reasons"])


# ---------------- decision upgrades
async def test_what_if_gives_a_price(agent):
    out = await run(agent, "cand_grey_jeans", 95)
    assert out["verdict"] == "think"
    assert out["what_if"], "a THINK should say what would change it"


async def test_contributions_explain_duplicate(agent):
    out = await run(agent, "cand_navy_shirt")
    assert out["contributions"]["you already own it"] < 0


async def test_need_for_occasion_answer_counts_as_gap(agent):
    a = await run(agent, "cand_grey_jeans", 95)
    b = await run(agent, "cand_grey_jeans", 95, need_for_occasion=True)
    assert b["score"] > a["score"] and b["fills_gap"]


async def test_low_photo_confidence_asks_to_confirm(agent):
    out = await run(agent, "cand_white_shirt", 79, ai_confidence=0.3)
    assert out["uncertain"] and out["question_key"] == "confirm_type"


def test_bandit_learns_a_preference(tmp_path):
    from modules.m06_smartbuy.bandit import PersonalThresholds
    pt = PersonalThresholds(path=tmp_path / "s.json", seed=0)
    for _ in range(200):
        arm = pt.choose("u")
        pt.update("u", arm, arm == -10)
    assert pt.best("u") == -10
    assert (tmp_path / "s.json").exists()


def test_learned_model_beats_chance():
    import numpy as np

    from modules.m06_smartbuy.learn import fit
    rng = np.random.default_rng(0)
    X = rng.random((90, 7))
    y = (X[:, 0] > 0.5).astype(int) * 2  # buy if feature 0 high, else skip
    m = fit(X, y)
    W, b = np.array(m["W"]), np.array(m["b"])
    acc = ((X @ W.T + b).argmax(1) == y).mean()
    assert acc > 0.85


def test_learned_mode_gives_probabilities():
    from modules.m06_smartbuy.agent import CONFIG, MODEL_FILE
    if not MODEL_FILE.exists():
        pytest.skip("no trained model: run python -m modules.m06_smartbuy.learn")
    import asyncio
    a = SmartBuyAgent({**CONFIG, "decision": "learned", "personalize": False})
    out = asyncio.run(a({"user_id": "usr_demo", "probe_image": "cand_navy_shirt", "price_tnd": 69}))
    assert out["decision_mode"] == "learned" and abs(sum(out["probabilities"].values()) - 1) < 0.01
    assert out["verdict"] == "skip"  # duplicates stay a hard rule
