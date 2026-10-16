from modules.m08_llm_layer.service import chat, parse, recommend
from modules.m08_llm_layer.taste import cosine, taste_profile


def _vec(*values: float) -> list[float]:
    norm = sum(value * value for value in values) ** 0.5
    return [value / norm for value in values]


def test_parse_pulls_weather_and_budget():
    out = parse({"user_id": "ada", "payload": {"message": "what should I wear in the rainy office under $80"}})
    assert out["mocked"] is False
    assert out["result"]["weather"] == "rainy"
    assert out["result"]["occasion"] == "office"
    assert out["result"]["budget"] == 80
    assert out["result"]["intent"] == "outfit"


def test_several_tastes_and_a_nearby_probe():
    vectors = {
        "tee": _vec(1, 0, 0),
        "jeans": _vec(0, 1, 0),
        "jacket": _vec(0, 0, 1),
    }
    events = [
        {"kind": "like", "piece_id": "tee", "at": 10},
        {"kind": "like", "piece_id": "jeans", "at": 11},
        {"kind": "like", "piece_id": "jacket", "at": 12},
    ]
    profile = taste_profile(events, vectors, seed=7)
    assert len(profile["tastes"]) >= 2
    center = [sum(taste[i] for taste in profile["tastes"]) / len(profile["tastes"]) for i in range(3)]
    assert cosine(profile["exploration"], center) > 0.85
    again = taste_profile(events, vectors, seed=7)
    assert cosine(profile["exploration"], again["exploration"]) > 0.999


def test_recommend_keeps_a_liked_piece_and_marks_memory():
    pieces = [
        {"id": "tee", "name": "Black tee", "category": "t-shirt", "vector": _vec(1, 0, 0), "size": "M", "price": 25, "stock": 1},
        {"id": "white", "name": "White tee", "category": "t-shirt", "vector": _vec(0.2, 0.9, 0), "size": "M", "price": 25, "stock": 1},
        {"id": "jeans", "name": "Jeans", "category": "jeans", "vector": _vec(0, 1, 0), "size": "32", "price": 60, "stock": 1},
    ]
    events = [{"kind": "like", "piece_id": "tee", "at": 5}, {"kind": "like", "piece_id": "jeans", "at": 6}]
    out = recommend({"user_id": "ada", "payload": {"pieces": pieces, "events": events, "size": "M", "budget": 80}})
    ids = [item["id"] for item in out["result"]["pieces"]]
    assert "tee" in ids
    assert len(out["result"]["tastes"]) >= 2
    assert out["result"]["exploration"] == "nearby"


def test_chat_explains_the_outfit():
    pieces = [
        {"id": "tee", "name": "Black tee", "category": "t-shirt", "vector": _vec(1, 0, 0), "size": "M", "price": 25, "stock": 1},
    ]
    out = chat({"user_id": "ada", "payload": {"message": "rainy office", "pieces": pieces}})
    assert "Black tee" in out["result"]["reply"]
    assert out["result"]["request"]["weather"] == "rainy"
    assert out["result"]["shops"]
