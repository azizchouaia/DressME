"""Mock of M2: fixed data in the real shape. Served while USE_MOCKS=true (or M02_USE_MOCK=true)."""

import datetime as dt

_ITEMS = {
    "m_top1": {
        "item_id": "m_top1",
        "category": "top",
        "subcategory": "shirt",
        "name": "white shirt",
        "colors": [{"name": "white", "hex": "#f4f2ee", "share": 1.0}],
        "image": None,
        "status": "available",
    },
    "m_bot1": {
        "item_id": "m_bot1",
        "category": "bottom",
        "subcategory": "pants",
        "name": "navy pants",
        "colors": [{"name": "navy", "hex": "#24324f", "share": 1.0}],
        "image": None,
        "status": "available",
    },
    "m_sho1": {
        "item_id": "m_sho1",
        "category": "shoes",
        "subcategory": "shoes",
        "name": "brown shoes",
        "colors": [{"name": "brown", "hex": "#7a5236", "share": 1.0}],
        "image": None,
        "status": "available",
    },
    "m_out1": {
        "item_id": "m_out1",
        "category": "outerwear",
        "subcategory": "jacket",
        "name": "beige jacket",
        "colors": [{"name": "beige", "hex": "#d8c8aa", "share": 1.0}],
        "image": None,
        "status": "available",
    },
    "m_top2": {
        "item_id": "m_top2",
        "category": "top",
        "subcategory": "t-shirt",
        "name": "black t-shirt",
        "colors": [{"name": "black", "hex": "#1f1f22", "share": 1.0}],
        "image": None,
        "status": "available",
    },
    "m_bot2": {
        "item_id": "m_bot2",
        "category": "bottom",
        "subcategory": "pants",
        "name": "blue pants",
        "colors": [{"name": "blue", "hex": "#3b6db3", "share": 1.0}],
        "image": None,
        "status": "available",
    },
}


def _outfit(i: int, ids: list[str], score: float, occasion: str) -> dict:
    slots = {_ITEMS[x]["category"]: x for x in ids}
    return {
        "outfit_id": f"mock{i}",
        "user_id": "mock",
        "items": ids,
        "slots": slots,
        "context": {
            "occasion": occasion,
            "date": dt.date.today().isoformat(),
            "weather": {"temp_c": 18.0, "condition": "clear"},
        },
        "scores": {"compatibility": 0.82, "style_match": 0.5, "weather_fit": 0.9},
        "score": score,
        "score_breakdown": {
            "compatibility": 0.82,
            "weather_fit": 0.9,
            "occasion_fit": 0.8,
            "mood_fit": 0.5,
            "style_match": 0.5,
            "novelty": 0.5,
            "rotation_penalty": 0.0,
            "forgotten_bonus": 0.0,
        },
        "reasons": ["The pieces work well together", "Right warmth for 18°C"],
        "explanation": "The pieces work well together. Right warmth for 18°C.",
        "forgotten_item_id": None,
        "source": "m02-mock",
    }


def _result(outfits: list[dict], occasion: str = "casual") -> dict:
    used = {i: _ITEMS[i] for o in outfits for i in o["items"]}
    return {
        "result": {
            "outfits": outfits,
            "items": used,
            "context": {
                "occasion": occasion,
                "date": dt.date.today().isoformat(),
                "weather": {"temp_c": 18.0, "condition": "clear"},
            },
            "weather_source": "mock",
        },
        "mocked": True,
    }


def _occasion(req: dict) -> str:
    return ((req.get("payload") or {}).get("context") or {}).get("occasion", "casual")


def recommend(req: dict) -> dict:
    occ = _occasion(req)
    return _result(
        [
            _outfit(1, ["m_top1", "m_bot1", "m_sho1", "m_out1"], 0.78, occ),
            _outfit(2, ["m_top2", "m_bot2", "m_sho1"], 0.71, occ),
        ],
        occ,
    )


def remix(req: dict) -> dict:
    return _result([_outfit(3, ["m_top2", "m_bot1", "m_sho1"], 0.69, _occasion(req))], _occasion(req))


def complete(req: dict) -> dict:
    return recommend(req)


def swap(req: dict) -> dict:
    return _result([_outfit(4, ["m_top1", "m_bot2", "m_sho1"], 0.74, _occasion(req))], _occasion(req))


def score(req: dict) -> dict:
    return _result([_outfit(5, ["m_top1", "m_bot1", "m_sho1"], 0.76, _occasion(req))], _occasion(req))
