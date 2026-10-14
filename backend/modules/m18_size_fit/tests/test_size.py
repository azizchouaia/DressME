from modules.m18_size_fit import service

CHARTS = {"B": {"top": [{"size": "M", "chest_cm": [96, 102]}], "bottom": [{"size": "40", "waist_cm": [81, 85]}]}}


def test_size_from_chest():
    assert service.advise(CHARTS, "B", "top", {"chest_cm": 98})["size"] == "M"


def test_unknown_brand_gives_nothing():
    assert service.advise(CHARTS, "Z", "top", {"chest_cm": 98}) is None
