from modules.m13_partner_links import service


def test_links_match_type_and_prefer_colour():
    shops = [{"name": "A", "promo_code": "X", "items": [
        {"name": "w", "subcategory": "shirt", "colour": "white", "price_tnd": 60, "url": "u1"},
        {"name": "n", "subcategory": "shirt", "colour": "navy", "price_tnd": 50, "url": "u2"},
        {"name": "j", "subcategory": "jeans", "colour": "white", "price_tnd": 40, "url": "u3"}]}]
    out = service.links(shops, "shirt", "white", None)
    assert [l["url"] for l in out] == ["u1", "u2"]
