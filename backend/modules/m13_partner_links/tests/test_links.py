from modules.m13_partner_links import service


def test_links_match_type_and_prefer_colour():
    shops = [{"name": "A", "promo_code": "X", "items": [
        {"name": "w", "subcategory": "shirt", "colour": "white", "price_tnd": 60, "url": "u1"},
        {"name": "n", "subcategory": "shirt", "colour": "navy", "price_tnd": 50, "url": "u2"},
        {"name": "j", "subcategory": "jeans", "colour": "white", "price_tnd": 40, "url": "u3"}]}]
    out = service.links(shops, "shirt", "white", None)
    assert [l["url"] for l in out] == ["u1", "u2"]


def test_one_per_shop_gives_a_real_choice():
    shops = [{"name": "A", "items": [{"name": "w", "subcategory": "shirt", "colour": "white", "price_tnd": 60, "url": "u1"},
                                     {"name": "w2", "subcategory": "shirt", "colour": "white", "price_tnd": 50, "url": "u2"}]},
             {"name": "B", "items": [{"name": "b", "subcategory": "shirt", "colour": "white", "price_tnd": 70, "url": "u3"}]}]
    out = service.links(shops, "shirt", "white", None, one_per_shop=True)
    assert [l["shop"] for l in out] == ["A", "B"]


def test_m7_catalogue_is_used_when_present():
    from pathlib import Path
    import pytest
    if not service.M7_CSV.is_file():
        pytest.skip("M7 catalogue not pulled")
    shops = service.load(Path("nowhere"))
    assert len(shops) > 10 and all(s["source"] == "m7" for s in shops)
    assert service.typical_prices(shops)["t-shirt"] > 0
