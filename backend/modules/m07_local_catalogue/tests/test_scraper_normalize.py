import pytest

from modules.m07_local_catalogue.scraper.normalize import (
    categorize,
    is_kids,
    join_sizes,
    main_color,
    origin_type,
)
from modules.m07_local_catalogue.scraper.run import balanced_pick


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Baskets blanches", "Sneakers"),
        ("Short basket en mesh finitions métal", "Short"),
        ("Maillot de Basket en Mesh à Broderies", "T-shirt & top"),
        ("Basket-ball short", "Short"),
        ("Adidas Samba", "Sneakers"),
        ("Chaussettes pour sneakers", "Accessoire"),
        ("T-shirt col V", "T-shirt & top"),
        ("Sweat-shirt oversize", "Pull"),
        ("Pul torsadé", "Pull"),
        ("Pantalon en maille", "Pantalon"),
        ("Robe en maille côtelée", "Robe"),
        ("Chemise en jean", "Chemise"),
        ("Short en jean", "Short"),
        ("Veste en jean", "Veste"),
        ("dengri dark blue", "Jean"),
        ("Robe avec ceinture", "Robe"),
        ("Set 3 Boucles d'oreilles", "Accessoire"),
        ("Set Femme en Laine", "Ensemble"),
        ("Jebba brodée", "Traditionnel"),
        ("جلباب الأناقة", "Traditionnel"),
        ("Coffret bougies", None),
    ],
)
def test_categorize(title, expected):
    assert categorize(title) == expected


def test_categorize_falls_back_to_shop_category_text():
    assert categorize("Ensemble Amwej") == "Ensemble"
    assert categorize("Amwej", "product ensemble") == "Ensemble"


def test_main_color_prefers_title_then_variants():
    assert main_color("Baskets blanches", ["Noir"]) == "Blanc"
    assert main_color("Jean slim", ["T00849-NOIRDEL"]) == "Noir"
    assert main_color("Jean slim", []) == "Bleu"
    assert main_color("Chemise Nour", ["T00849-NOIRDEL"]) == "Noir"
    assert main_color("Chemise Nour", []) == ""


def test_join_sizes_dedupes_and_normalises():
    assert join_sizes(["38", "39", "39", "Taille 40"]) == "38, 39, 40"
    assert join_sizes(["36_37", "s", "M"]) == "36/37, S, M"
    assert join_sizes(["Default Title"]) == ""
    assert join_sizes(["TU"]) == "Taille unique"


def test_kids_and_origin():
    assert is_kids("Sandale fillette")
    assert not is_kids("Robe longue femme")
    assert origin_type("local_retailer", "Nike", "Air Max 90") == "international_brand"
    assert origin_type("local_brand", "", "Jebba brodée") == "local_brand"


def test_balanced_pick_spreads_categories():
    rows = [("Sneakers", i) for i in range(50)] + [("Robe", i) for i in range(5)]
    picked = balanced_pick(rows, 10)
    assert len(picked) == 10
    assert sum(1 for cat, _ in picked if cat == "Robe") == 5
