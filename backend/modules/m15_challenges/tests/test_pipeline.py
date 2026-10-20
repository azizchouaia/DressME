import pytest

from modules.m15_challenges.agent import ChallengesAgent
from modules.m15_challenges.pipeline import feasibility, leaderboard, progress, recommend, rules, suggest
from modules.m15_challenges.wardrobe import MockWardrobe
from shared.base_agent import AgentError
from shared.schemas import Garment

W = {g.item_id: g for g in MockWardrobe().items("u")}


def g(*ids: str) -> list[Garment]:
    return [W[i] for i in ids]


class FakeShare:
    """Stands in for M10 so these tests do not need Pillow."""

    def __init__(self):
        self.calls = []

    async def __call__(self, payload: dict) -> dict:
        self.calls.append(payload)
        n = len(self.calls)
        return {
            "image_url": f"/m10/cards/c{n}/image",
            "share_url": f"https://dressme.tn/s/c{n}",
            "caption": "ok",
        }


# ---------- rules ----------
def test_no_repeat():
    prev = [(1, g("itm_t1", "itm_b1", "itm_s1"))]
    v = rules.no_repeat({}, g("itm_t2", "itm_b1", "itm_s2"), prev)
    assert v == ["straight jeans already worn on day 1"]
    assert rules.no_repeat({}, g("itm_t2", "itm_b2", "itm_s2"), prev) == []


def test_color_theme_all_and_any():
    p = {"colors": ["black", "white"], "mode": "all"}
    assert rules.color_theme(p, g("itm_t1", "itm_b2", "itm_s2"), []) == []
    assert len(rules.color_theme(p, g("itm_t1", "itm_b1"), [])) == 1  # jeans are blue
    assert rules.color_theme({**p, "mode": "any"}, g("itm_t1", "itm_b1"), []) == []


def test_category_required_and_local_brand():
    assert rules.category_required({"categories": ["traditional"]}, g("itm_tr1", "itm_s4"), []) == []
    assert rules.category_required({"categories": ["traditional"]}, g("itm_t1"), []) != []
    assert rules.local_brand({"min": 1}, g("itm_t3", "itm_b1"), []) == []
    assert rules.local_brand({"min": 1}, g("itm_t1", "itm_b1"), []) != []


def test_capsule_limit():
    prev = [(1, g("itm_t1", "itm_b1", "itm_s1")), (2, g("itm_t2", "itm_b2", "itm_s2"))]
    assert rules.capsule_limit({"max_distinct": 7}, g("itm_t1", "itm_b2", "itm_s3"), prev) == []
    assert rules.capsule_limit({"max_distinct": 6}, g("itm_t3", "itm_b1", "itm_s1"), prev) != []


def test_min_items():
    assert rules.min_items({"min": 3}, g("itm_t1", "itm_b1"), []) != []


# ---------- feasibility ----------
def test_disjoint_outfits():
    # 6 tops, 4 bottoms, 2 one-pieces (dress + jebba) → 6 body looks, but only 5 pairs of shoes
    assert feasibility.disjoint_outfits(list(W.values())) == 5


def test_feasibility_7x7_limited_by_shoes():
    score, reason = feasibility.run([{"type": "no_repeat"}], 7, list(W.values()))
    assert score == pytest.approx(5 / 7, abs=0.01)
    assert "shoes" in reason


def test_feasibility_monochrome_and_missing_category():
    mono = [{"type": "color_theme", "params": {"colors": ["black", "white", "grey"], "mode": "all"}}]
    assert feasibility.run(mono, 5, list(W.values()))[0] == 1.0
    no_trad = [x for x in W.values() if x.category.value != "traditional"]
    assert (
        feasibility.run(
            [{"type": "category_required", "params": {"categories": ["traditional"]}}], 4, no_trad
        )[0]
        == 0.0
    )


# ---------- suggestion ----------
def test_suggestion_respects_rules():
    r = [{"type": "no_repeat"}, {"type": "min_items", "params": {"min": 2}}]
    prev = [(1, g("itm_t6", "itm_b4", "itm_s4"))]
    s = suggest.run(r, list(W.values()), prev)
    assert s and not set(s) & {"itm_t6", "itm_b4", "itm_s4"}
    assert not rules.run(r, g(*s), prev)


def test_suggestion_for_traditional_friday():
    r = [{"type": "category_required", "params": {"categories": ["traditional"]}}]
    assert "itm_tr1" in suggest.run(r, list(W.values()), [])


# ---------- progress / leaderboard / recommend ----------
def test_progress_streak_points_badges():
    entries = [{"day": d, "valid": v} for d, v in [(1, True), (2, True), (3, True), (4, False), (5, True)]]
    p = progress.run(entries, 7)
    assert (p["valid_days"], p["streak"], p["next_day"]) == (4, 1, 6)
    assert p["points"] == 4 * 10 + 5
    assert p["badges"] == ["Starter", "On a roll"]


def test_bayesian_leaderboard_beats_one_viral_post():
    rows = [
        {"user_id": "steady", "valid_days": 7, "likes": 21, "posts": 7},
        {"user_id": "viral", "valid_days": 1, "likes": 40, "posts": 1},
    ]
    ranked = leaderboard.run(rows)
    assert ranked[0]["user_id"] == "steady"


def test_recommend_prefers_feasible_challenges():
    ch = [
        {"challenge_id": "a", "feasibility": 1.0, "participants": 2, "tags": ["minimal"]},
        {"challenge_id": "b", "feasibility": 0.2, "participants": 50, "tags": []},
    ]
    assert recommend.run(ch, {"minimal"})[0]["challenge_id"] == "a"


# ---------- agent end-to-end ----------
async def test_full_week_flow():
    share = FakeShare()
    agent = ChallengesAgent(share_agent=share)
    out = await agent({"user_id": "amen", "action": "join", "challenge_id": "ch_7x7"})
    assert out["progress"]["next_day"] == 1

    r1 = await agent.submit("amen", "ch_7x7", ["itm_t1", "itm_b1", "itm_s1"])
    assert r1.valid and r1.post and r1.post.share_url and share.calls[0]["kind"] == "challenge"
    assert r1.suggestion and "itm_b1" not in r1.suggestion

    r2 = await agent.submit("amen", "ch_7x7", ["itm_t2", "itm_b1", "itm_s2"])  # jeans again
    assert not r2.valid and "straight jeans already worn on day 1" in r2.violations[0]
    assert r2.post is None and r2.day == 2

    r3 = await agent.submit("amen", "ch_7x7", ["itm_t2", "itm_b2", "itm_s2"])
    assert r3.valid and r3.day == 3 and r3.progress.valid_days == 2

    with pytest.raises(AgentError):
        await agent.submit("amen", "ch_7x7", ["itm_t3", "itm_b3", "itm_s3"], day=3)  # already logged
    with pytest.raises(AgentError):
        await agent.submit("amen", "ch_7x7", ["not_mine"])


async def test_must_join_first_and_unknown_challenge():
    agent = ChallengesAgent(share_agent=FakeShare())
    with pytest.raises(AgentError):
        await agent.submit("x", "ch_7x7", ["itm_t1"])
    with pytest.raises(AgentError):
        await agent({"user_id": "x", "action": "join", "challenge_id": "nope"})


async def test_leaderboard_likes_and_feed():
    agent = ChallengesAgent(share_agent=FakeShare())
    for u in ("a", "b"):
        agent.join(u, "ch_7x7")
    pa = (await agent.submit("a", "ch_7x7", ["itm_t1", "itm_b1", "itm_s1"])).post
    await agent.submit("b", "ch_7x7", ["itm_t1", "itm_b1", "itm_s1"])
    await agent.submit("b", "ch_7x7", ["itm_t2", "itm_b2", "itm_s2"])
    assert agent.like(pa.post_id, "b") == 1
    assert agent.like(pa.post_id, "b") == 0  # toggle
    board = agent.leaderboard("ch_7x7")
    assert [r.user_id for r in board] == ["b", "a"]
    assert len(agent.feed("ch_7x7")) == 3


async def test_recommend_and_list_through_run():
    agent = ChallengesAgent(share_agent=FakeShare())
    rec = (await agent({"user_id": "amen", "action": "recommend"}))["challenges"]
    assert len(rec) == 6 and all(0 <= c["feasibility"] <= 1 for c in rec)
    assert rec == sorted(rec, key=lambda c: -c["match_score"])


async def test_real_share_card_is_created():
    pytest.importorskip("PIL")
    from modules.m10_share_cards.agent import ShareAgent

    share = ShareAgent()
    agent = ChallengesAgent(share_agent=share)
    agent.join("amen", "ch_local")
    r = await agent.submit("amen", "ch_local", ["itm_t3", "itm_b3", "itm_s3"])
    assert r.valid and r.post.card_image_url.startswith("/m10/cards/")
    assert share.store.get_png(r.post.card_image_url.split("/")[3])
