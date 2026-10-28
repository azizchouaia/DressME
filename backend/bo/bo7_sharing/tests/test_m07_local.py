"""BO7 on M7 (local catalogue, BO6): Tunisian shops for tags, and 'shop this look in Tunisia'."""

import asyncio

from bo.bo7_sharing import m07_local


def test_query_from_a_piece():
    assert m07_local.query_for("grey and white blouse", "grey") == "blouse gris"
    assert m07_local.query_for("red embroidered balgha", "red") == "balgha rouge"
    assert m07_local.shop_id("Chill&Lit") == "m07:chill-lit"


def test_shops_and_shop_the_look():
    shops = asyncio.run(m07_local.shops())
    if not shops:  # M7 not available in this environment
        return
    assert all({"shop", "kind", "url"} <= set(s) for s in shops)
    look = asyncio.run(m07_local.shop_the_look([{"item_id": "a", "name": "white shirt", "color": "white"}]))
    assert look[0]["item_id"] == "a" and look[0]["query"] == "chemise blanc"
    for p in look[0]["products"]:
        assert p["shop"] in {s["shop"] for s in shops} and p["kind"].startswith("Tunisian")
