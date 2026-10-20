"""if/else outfit check: one piece per slot, body covered, one-piece replaces top and bottom."""

import pytest

from modules.m15_challenges.agent import ChallengesAgent
from modules.m15_challenges.pipeline import outfit, suggest
from shared.base_agent import AgentError
from shared.schemas import Garment


def g(item_id: str, category: str, sub: str | None = None) -> Garment:
    return Garment(item_id=item_id, user_id="u", image_raw="x", category=category, subcategory=sub)


TOP, BOTTOM, SHOES = g("t", "top", "t-shirt"), g("b", "bottom", "shorts"), g("s", "shoes", "black shoes")


def test_slots():
    assert outfit.slot(g("1", "accessory", "red chechia")) == "hat"
    assert outfit.slot(g("2", "accessory", "alfa koffa basket bag")) == "bag"
    assert outfit.slot(g("3", "traditional", "grey wool jebba")) == "one_piece"
    assert outfit.slot(g("4", "traditional", "kachabia")) == "layer"
    assert outfit.slot(g("5", "shoes", "yellow balgha")) == "shoes"


def test_valid_outfits():
    assert outfit.check([TOP, BOTTOM, SHOES, g("h", "accessory", "black hat")]) == []
    jebba, chechia = g("j", "traditional", "white jebba"), g("c", "accessory", "red chechia")
    assert outfit.check([jebba, chechia, SHOES]) == []
    assert outfit.check([TOP, BOTTOM, g("k", "traditional", "kachabia")]) == []  # layer over clothes


def test_impossible_outfits():
    hats = [g(f"h{i}", "accessory", f"hat {i}") for i in range(3)]
    assert any("only 1 hat" in p for p in outfit.check([TOP, BOTTOM, *hats]))
    two_shoes = outfit.check([TOP, BOTTOM, SHOES, g("s2", "shoes", "grey shoes")])
    assert any("pair of shoes" in p for p in two_shoes)
    assert any("covers top and bottom" in p for p in outfit.check([g("j", "traditional", "jebba"), TOP]))
    assert any("needs a bottom" in p for p in outfit.check([TOP, SHOES]))
    assert any("only 1 top" in p for p in outfit.check([TOP, g("t2", "top", "black hoodie"), BOTTOM]))


def test_suggestion_is_always_wearable():
    wardrobe = [TOP, BOTTOM, SHOES, g("s2", "shoes", "grey"), g("j", "traditional", "jebba"), g("t2", "top")]
    rules = [{"type": "category_required", "params": {"categories": ["traditional"]}}]
    ids = suggest.run(rules, wardrobe, [])
    picked = [x for x in wardrobe if x.item_id in ids]
    assert outfit.check(picked) == [] and "j" in ids and "t" not in ids


async def test_agent_refuses_an_impossible_outfit_without_using_the_day():
    agent = ChallengesAgent()
    items = agent.wardrobe.items("amen")
    shoes = [x.item_id for x in items if x.category.value == "shoes"][:2]
    await agent({"user_id": "amen", "action": "join", "challenge_id": "ch_7x7"})
    with pytest.raises(AgentError, match="cannot be worn"):
        await agent.submit("amen", "ch_7x7", shoes)
    assert agent.progress("amen", "ch_7x7").days_logged == 0


def test_suggestion_rotates_pieces_already_worn_in_the_challenge():
    t2, b2, s2 = g("t2", "top", "polo"), g("b2", "bottom", "serwal"), g("s2", "shoes", "balgha")
    ids = suggest.run([], [TOP, BOTTOM, SHOES, t2, b2, s2], [(1, [TOP, BOTTOM, SHOES])])
    assert set(ids) == {"t2", "b2", "s2"}
