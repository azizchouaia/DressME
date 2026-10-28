"""BO7 on the real wardrobe: M15 reads M1 (mock), the demo garments are added through M1's API."""

import asyncio

import pytest

from bo.bo7_sharing import m01_seed
from modules.m01_wardrobe import mock as m1
from modules.m01_wardrobe.contract import ItemsRequest, ItemUpdate
from modules.m15_challenges.agent import ChallengesAgent
from modules.m15_challenges.wardrobe import M1Wardrobe
from shared.base_agent import AgentError


@pytest.fixture
def wardrobe(monkeypatch, tmp_path):
    monkeypatch.setenv("M01_DATA_DIR", str(tmp_path))
    m1._reset()
    w = M1Wardrobe(seeder=m01_seed.seed, seed_users={"amen"}, local_brands=m01_seed.local_brands(),
                   resolve=m01_seed.resolve)
    monkeypatch.setattr(M1Wardrobe, "impl", staticmethod(lambda: m1))
    yield w
    m1._reset()


def test_demo_user_gets_the_demo_garments_once(wardrobe):
    items = wardrobe.items("amen")
    assert len(items) == len(m01_seed.demo_garments()) >= 60
    assert len(wardrobe.items("amen")) == len(items)  # not seeded twice
    total = asyncio.run(m1.items(ItemsRequest(user_id="amen"))).total
    assert total == len(items)  # really stored in M1
    g = items[0]
    assert g.image_raw.startswith("/bo7/demo/photos/") and g.image_cutout.endswith(".png")
    assert any(x.local_tag == "Medina artisans" for x in items)  # Tunisian maker read from M1 `brand`


def test_other_users_start_with_an_empty_wardrobe(wardrobe):
    assert wardrobe.items("someone_new") == []


def test_only_active_pieces_and_maker_from_brand(wardrobe):
    items = wardrobe.items("amen")
    first = items[0]
    asyncio.run(m1.update_item("amen", first.item_id, ItemUpdate(status="donated")))
    assert first.item_id not in {g.item_id for g in wardrobe.items("amen")}  # given away: not in challenges
    other = items[1]
    asyncio.run(m1.update_item("amen", other.item_id, ItemUpdate(brand="Zara")))
    assert next(g for g in wardrobe.items("amen") if g.item_id == other.item_id).local_tag is None


async def test_challenge_day_on_the_m1_wardrobe(wardrobe):
    agent = ChallengesAgent(wardrobe=wardrobe)
    pieces = await asyncio.to_thread(wardrobe.items, "amen")
    top = next(g for g in pieces if g.category.value == "top")
    bottom = next(g for g in pieces if g.category.value == "bottom")
    shoes = next(g for g in pieces if g.category.value == "shoes")
    await agent({"user_id": "amen", "action": "join", "challenge_id": "ch_7x7"})
    r = await agent.submit("amen", "ch_7x7", [top.item_id, bottom.item_id, shoes.item_id], share=False)
    assert r.valid and r.progress.valid_days == 1
    with pytest.raises(AgentError, match="Not in your wardrobe"):
        await agent.submit("amen", "ch_7x7", ["itm_not_mine"], share=False)
