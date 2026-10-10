from orchestrator.registry import AGENTS


def test_all_agents_registered():
    assert set(AGENTS) == {"vision", "stylist", "profile", "smartbuy", "localshop", "tryon"}
