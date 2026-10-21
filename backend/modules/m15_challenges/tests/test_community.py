"""Comments with if/else moderation, and ML nudges for participants at risk."""

import pytest

from modules.m15_challenges.agent import ChallengesAgent
from modules.m15_challenges.pipeline import moderation
from shared.base_agent import AgentError


class FakeShare:
    async def __call__(self, payload):
        return {"image_url": "/img", "share_url": "https://dressme.tn/s/x", "caption": "ok"}


@pytest.mark.parametrize(
    "text,ok",
    [
        ("Love the jebba with the white sneakers!", True),
        ("Ya3tik essa7a, lebsa mezyena", True),
        ("", False),
        ("check www.spam.com for deals", False),
        ("THIS IS THE BEST OUTFIT EVER", False),
        ("waaaaaaaw", False),
        ("this is ugly", False),
        ("lebsa mekhyeb", False),
        ("x" * 300, False),
    ],
)
def test_moderation(text, ok):
    assert moderation.check(text)[0] is ok


async def test_comment_flow_and_count():
    a = ChallengesAgent(share_agent=FakeShare())
    a.join("u", "ch_7x7")
    r = await a.submit("u", "ch_7x7", ["itm_t1", "itm_b1", "itm_s1"])
    pid = r.post.post_id
    a.comment(pid, "friend", "Nice combo!")
    with pytest.raises(AgentError, match="Comment refused"):
        a.comment(pid, "troll", "so ugly")
    assert [c.text for c in a.comments(pid)] == ["Nice combo!"]
    assert a.feed("ch_7x7")[0].comments == 1


async def test_nudges_rank_by_ml_probability():
    a = ChallengesAgent(share_agent=FakeShare())
    for u in ("steady", "struggling", "new"):
        a.join(u, "ch_7x7")
    await a.submit("steady", "ch_7x7", ["itm_t1", "itm_b1", "itm_s1"])
    await a.submit("steady", "ch_7x7", ["itm_t2", "itm_b2", "itm_s2"])
    await a.submit("struggling", "ch_7x7", ["itm_t1", "itm_b1", "itm_s1"])
    await a.submit("struggling", "ch_7x7", ["itm_t1", "itm_b1", "itm_s1"])  # repeat → not counted
    all_ = a.nudges("ch_7x7", include_on_track=True)
    probs = [n.completion_probability for n in all_]
    assert probs == sorted(probs) and {n.user_id for n in all_} == {"steady", "struggling", "new"}
    by = {n.user_id: n for n in all_}
    assert by["struggling"].completion_probability < by["steady"].completion_probability
    assert by["struggling"].suggestion and "Day 3" in by["struggling"].message
    assert all(n.risk != "on_track" for n in a.nudges("ch_7x7"))
