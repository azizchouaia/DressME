"""User / sponsor challenges and the finisher card."""

import pytest

from modules.m15_challenges.agent import ChallengesAgent
from modules.m15_challenges.contract import ChallengeDraft, ChallengeRule
from shared.base_agent import AgentError


class FakeShare:
    def __init__(self):
        self.calls = []

    async def __call__(self, payload):
        self.calls.append(payload)
        return {
            "image_url": f"/img/{len(self.calls)}",
            "share_url": "https://dressme.tn/s/x",
            "caption": "ok",
        }


def draft(**kw):
    base = {
        "title": "Blue week",
        "description": "Wear one blue piece every day.",
        "duration_days": 3,
        "rules": [ChallengeRule(type="color_theme", params={"colors": ["blue"], "mode": "any"})],
        "sponsor": "Sidi Linen Co.",
    }
    return ChallengeDraft(**{**base, **kw})


def test_create_challenge_is_listed_with_feasibility():
    a = ChallengesAgent(share_agent=FakeShare())
    v = a.create_challenge("brand_sidi", draft())
    assert v.challenge_id.startswith("ch_blue_week_") and v.created_by == "brand_sidi"
    assert v.feasibility is not None
    assert any(c.challenge_id == v.challenge_id for c in a.list_challenges("amen"))
    with pytest.raises(AgentError, match="already exists"):
        a.create_challenge("x", draft())


@pytest.mark.parametrize(
    "rules,msg",
    [
        ([ChallengeRule(type="color_theme", params={"colors": ["gold"]})], "unknown colour"),
        ([ChallengeRule(type="no_repeat"), ChallengeRule(type="capsule_limit")], "contradict"),
        ([ChallengeRule(type="min_items", params={"min": 9})], "between 1 and 6"),
    ],
)
def test_invalid_rules_are_rejected(rules, msg):
    with pytest.raises(AgentError, match=msg):
        ChallengesAgent(share_agent=FakeShare()).create_challenge("u", draft(title="T " + msg, rules=rules))


async def test_last_day_produces_finisher_card():
    share = FakeShare()
    a = ChallengesAgent(share_agent=share)
    v = a.create_challenge("u", draft(rules=[ChallengeRule(type="no_repeat")]))
    a.join("u", v.challenge_id)
    outfits = [["itm_t1", "itm_b1", "itm_s1"], ["itm_t2", "itm_b2", "itm_s2"], ["itm_t3", "itm_b3", "itm_s3"]]
    for i, o in enumerate(outfits):
        r = await a.submit("u", v.challenge_id, o)
        assert (r.completion_card_url is None) == (i < 2)
    assert "Finisher" in r.progress.badges
    fin = share.calls[-1]
    assert fin["title"].endswith("completed!") and fin["format"] == "story"
    assert {s["label"] for s in fin["stats"]} == {"valid days", "best streak", "points", "likes"}
    assert any(s.name == "Finisher card" for s in r.pipeline)
