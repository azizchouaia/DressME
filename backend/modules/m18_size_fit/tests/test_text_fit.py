from modules.m18_size_fit import text_fit as t

BRANDS = ["Medina Atelier", "Carthage Denim Co."]


def test_english_two_pieces_with_body_part():
    out = t.parse_rules("I wear M at Medina Atelier but it's tight on the shoulders, "
                        "and my 40 jeans from Carthage Denim are a bit loose", BRANDS)
    assert out["refs"] == [
        {"brand": "Medina Atelier", "size": "M", "category": "top", "fit": "tight", "part": "shoulders"},
        {"brand": "Carthage Denim Co.", "size": "40", "category": "bottom", "fit": "loose", "part": None}]


def test_french_strong_word_and_preference():
    out = t.parse_rules("Chez Medina Atelier je porte L, trop serré. J'aime les vêtements larges", BRANDS)
    assert out["refs"][0]["fit"] == "extremely_tight" and out["like_fit"] == "loose"


def test_tunisian_darija():
    out = t.parse_rules("M mta3 Medina Atelier dayyeq barcha", BRANDS)
    assert out["refs"][0]["fit"] == "extremely_tight"


def test_unclear_text_finds_nothing():
    out = t.parse_rules("my shirts are tight", BRANDS)
    assert out["refs"] == [] and out["unclear"]


def test_llm_answer_is_checked():
    out = t._clean({"refs": [{"brand": "medina atelier", "size": "m", "fit": "tight", "category": "top"},
                             {"brand": "Unknown", "size": "M", "fit": "tight"},
                             {"brand": "Medina Atelier", "size": "huge", "fit": "tight"},
                             {"brand": "Medina Atelier", "size": "L", "fit": "weird"}],
                    "like_fit": "oversized"}, BRANDS)
    assert [(r["brand"], r["size"]) for r in out["refs"]] == [("Medina Atelier", "M")]
    assert out["like_fit"] == "oversized"


def test_llm_off_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(t, "parse_llm", lambda *a, **k: None)
    assert t.parse("my shirts are tight", BRANDS)["method"] == "rules"
