"""Real teammates' modules with the mock as safety net."""

from modules.m06_smartbuy.clients.real import HybridClients, _from_m1


def test_demo_candidate_falls_back_to_mock():
    cl = HybridClients(["m1", "m2", "m7"])
    c = cl.classify("custom:shirt:white")
    assert c["subcategory"] == "shirt" and cl.sources["classify"] == "mock"
    assert cl.items("usr_sarra") and cl.sources["items"] == "mock"


def test_m2_waits_for_1024_vectors():
    cl = HybridClients(["m2"])
    c = cl.classify("custom:jeans:blue")
    assert isinstance(cl.recommend_with("usr_sarra", c), list) and cl.sources["recommend_with"] == "mock"


def test_m1_item_is_mapped_to_smartbuy_types():
    it = _from_m1({"item_id": "i1", "subcategory": "linen shirt", "colors": [{"name": "navy"}], "brand": "Zara", "size": "M"})
    assert (it["subcategory"], it["colour"], it["category"], it["size"]) == ("shirt", "navy", "top", "M")
