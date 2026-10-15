from modules.m18_size_fit import service

CHARTS = {"B": {"top": [{"size": "M", "chest_cm": [96, 102]}], "bottom": [{"size": "40", "waist_cm": [81, 85]}]}}


def test_size_from_chest():
    assert service.advise(CHARTS, "B", "top", {"chest_cm": 98})["size"] == "M"


def test_unknown_brand_gives_nothing():
    assert service.advise(CHARTS, "Z", "top", {"chest_cm": 98}) is None


CH2 = {"A": {"top": [{"size": "S", "chest_cm": [89, 95]}, {"size": "M", "chest_cm": [96, 102]},
                     {"size": "L", "chest_cm": [103, 109]}, {"size": "XL", "chest_cm": [110, 116]}]},
       "B": {"top": [{"size": "M", "chest_cm": [98, 104]}, {"size": "L", "chest_cm": [105, 111]}]}}


def test_fit_words_normal_keeps_size():
    body = {"fit_refs": [{"brand": "A", "size": "M", "category": "top", "fit": "normal"}]}
    assert service.advise(CH2, "A", "top", body)["size"] == "M"


def test_tight_goes_up():
    body = {"fit_refs": [{"brand": "A", "size": "M", "category": "top", "fit": "extremely_tight"}]}
    assert service.advise(CH2, "A", "top", body)["size"] == "L"


def test_like_oversized_goes_up():
    body = {"fit_refs": [{"brand": "A", "size": "M", "category": "top", "fit": "normal"}], "like_fit": "oversized"}
    assert service.advise(CH2, "A", "top", body)["size"] == "L"


def test_numbers_win_over_words():
    body = {"chest_cm": 92, "fit_refs": [{"brand": "A", "size": "XL", "category": "top", "fit": "normal"}]}
    assert service.advise(CH2, "A", "top", body)["size"] == "S"
