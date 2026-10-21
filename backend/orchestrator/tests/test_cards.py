"""Every module has a card. The planner can call the agents, including taste."""

import importlib

from orchestrator.registry import get_tools

REQUIRED = {"name", "version", "owner", "module", "role", "rules", "when_to_use", "when_not_to_use", "skills"}
AGENTS = {
    "m01_wardrobe": "wardrobe",
    "m02_recommendation": "stylist",
    "m05_style_profile": "profile",
    "m06_smartbuy": "smartbuy",
    "m07_local_catalogue": "localshop",
    "m09_avatar_3d": "tryon",
    "m10_share_cards": "share",
    "m11_trip_planner": "trips",
    "m15_challenges": "challenges",
    "m19_taste": "taste",
}
SKILLS = {
    "m03_wear_log": "stylist",
    "m04_scheduler": "stylist",
    "m08_llm_layer": "orchestrator",
    "m12_style_evolution": "profile",
    "m13_partner_links": "smartbuy",
    "m14_stylist_mode": "localshop",
    "m16_sustainability": "trips",
    "m17_capsule": "stylist",
    "m18_size_fit": "smartbuy",
}


def test_every_module_has_a_card_and_only_agents_are_tools():
    for module, name in {**AGENTS, **SKILLS}.items():
        card = importlib.import_module(f"modules.{module}.identity").CARD
        assert REQUIRED <= set(card)
        assert card["module"].startswith("M")
        assert card["owner"].startswith("BO") or card["owner"] == "BO1/BO2"
        if module in SKILLS:
            assert card["agent"] == SKILLS[module]
        else:
            assert card["name"] == name
    names = sorted(tool.name for tool in get_tools())
    assert names == sorted(AGENTS.values())
