from modules.m07_local_catalogue.scraper.clean import find_duplicates, normalize_sizes, url_status
from modules.m07_local_catalogue.taxonomy import city_from_text, classify, subcategory_from_text


def test_sizes_one_notation_sorted():
    assert normalize_sizes("XL, S, 2XL, M") == ("S, M, XL, XXL", "letter", False)
    assert normalize_sizes("43, 40, 42.5, 41") == ("40, 41, 42.5, 43", "numeric", False)
    assert normalize_sizes("ST") == ("Taille unique", "one_size", False)
    assert normalize_sizes("XL/2XL, S/M") == ("S/M, XL/XXL", "letter", False)
    assert normalize_sizes("") == ("", "", False)
    assert normalize_sizes("12 ANS")[2] is True


def test_duplicates_need_same_photo_name_and_price():
    def row(shop, name, price, h, available="true"):
        return {
            "shop_name": shop,
            "product_name": name,
            "price_tnd": price,
            "_dhash": h,
            "available": available,
            "size": "S, M",
        }

    rows = [
        row("Corella", "Jilbab qualité", 52.0, 0b1010),
        row("Apparel", "jilbab qualite", 52.0, 0b1011),  # same piece sold by two shops -> duplicate
        row("HA", "Basket Femme", 59.99, 0xFF00),
        row("HA", "Basket Femme", 59.99, 0x00FF),  # same generic name, other photo -> kept
    ]
    assert find_duplicates(rows) == {1: 0}


def test_url_status():
    assert url_status(200, "https://s.tn/products/a", "https://s.tn/products/a") == "ok"
    assert url_status(404, "https://s.tn/p", "https://s.tn/p") == "dead"
    assert url_status(200, "https://s.tn/products/a", "https://s.tn/") == "dead"  # redirected home
    assert url_status(429, "https://s.tn/p", "https://s.tn/p") == "http_429"


def test_common_nomenclature():
    for word in ("baskets", "sneakers", "basket blanche", "Adidas Samba"):
        assert subcategory_from_text(word) == "sneakers"
    assert classify("Accessoire", "Ceinture homme cuir") == ("accessory", "belt", "Ceintures")
    assert city_from_text("une robe à la marsa") == "La Marsa"
    assert city_from_text("livraison partout en Tunisie") is None
