"""Mock of M17: fixed data in the real shape. Served while USE_MOCKS=true (or M17_USE_MOCK=true)."""

import datetime as dt

_PIECES = [
    ("m_top1", "white shirt", "top"),
    ("m_top2", "black t-shirt", "top"),
    ("m_top3", "grey knit", "top"),
    ("m_top4", "striped shirt", "top"),
    ("m_bot1", "navy pants", "bottom"),
    ("m_bot2", "jeans", "bottom"),
    ("m_bot3", "black skirt", "bottom"),
    ("m_sho1", "brown shoes", "shoes"),
    ("m_sho2", "white sneakers", "shoes"),
    ("m_out1", "beige trench", "outerwear"),
    ("m_out2", "navy blazer", "outerwear"),
    ("m_dre1", "black dress", "dress"),
]


def _outfit(ids: list[str], value: float, occ: list[str]) -> dict:
    return {
        "items": ids,
        "value": value,
        "occasions": occ,
        "compatibility": 0.8,
        "weather_fit": 0.9,
        "occasion_fit": {o: 0.8 for o in occ},
    }


def _result(start: dt.date, days: int) -> dict:
    outs = [
        _outfit(["m_top1", "m_bot1", "m_sho1"], 0.86, ["work"]),
        _outfit(["m_top2", "m_bot2", "m_sho2"], 0.83, ["casual"]),
        _outfit(["m_top3", "m_bot3", "m_sho1", "m_out1"], 0.8, ["work", "casual"]),
    ]
    plan = [
        {
            "date": (start + dt.timedelta(k)).isoformat(),
            "weekday": "",
            "occasion": "work",
            "reason": "weekday default",
            "outfit": outs[k % 3],
        }
        for k in range(days)
    ]
    return {
        "result": {
            "season": "autumn",
            "occasions": ["casual", "work"],
            "size": 12,
            "pieces": [
                {"item_id": i, "name": n, "category": c, "image": None, "outfits": 3} for i, n, c in _PIECES
            ],
            "outfits": outs,
            "n_outfits": 3,
            "by_occasion": {"casual": 2, "work": 2},
            "unused_pieces": [],
            "graph_edges": [{"items": ["m_bot1", "m_top1"], "compatibility": 0.9}],
            "items": {i: {"name": n, "category": c, "image": None} for i, n, c in _PIECES},
            "method": "ilp",
            "comparison": {"ilp": {"n_outfits": 3, "value": 2.49}},
            "minimums": {"top": 4},
            "plan": plan,
            "plan_stats": {"days": days, "different_outfits": 3, "max_repeats": days // 3 + 1},
        },
        "mocked": True,
    }


def capsule(req: dict) -> dict:
    return _result(dt.date.today(), 30)


def plan_capsule(req: dict) -> dict:
    return _result(dt.date.today(), 30)
