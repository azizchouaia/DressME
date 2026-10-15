import pytest

from modules.m07_local_catalogue.scraper.normalize import (
    categorize,
    is_kids,
    is_non_fashion,
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


@pytest.mark.parametrize(
    ("name", "dropped"),
    [
        ("Vase céramique fleur design 14 cm", True),  # decor sold by artisan marketplaces
        ("Kaak warka pistache", True),  # food
        ("Porte clé", True),
        ("Ceinture et porte clé en cuir marron grainé", False),  # a piece + a key ring: kept
        ("Collier a pendentif de cadre de photo doré", False),
        ("Sandales couleur chocolat", False),  # colour names are not food
    ],
)
def test_non_fashion(name, dropped):
    assert is_non_fashion(name) is dropped


def test_foreign_watch_and_lingerie_labels():
    assert origin_type("local_retailer", "Montre Bigotti") == "international_brand"
    assert origin_type("local_brand", "Soutien-gorge Simone Perele") == "international_brand"
    assert origin_type("local_brand", "Collier maille omega") == "local_brand"


def test_balanced_pick_spreads_categories():
    rows = [("Sneakers", i) for i in range(50)] + [("Robe", i) for i in range(5)]
    picked = balanced_pick(rows, 10)
    assert len(picked) == 10
    assert sum(1 for cat, _ in picked if cat == "Robe") == 5
