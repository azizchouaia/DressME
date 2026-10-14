"""Mock of M3: fixed data in the real shape. Served while USE_MOCKS=true (or M03_USE_MOCK=true)."""

import datetime as dt

_T = dt.date.today()


def _d(days: int) -> str:
    return (_T - dt.timedelta(days=days)).isoformat()


_ENTRY = {
    "entry_id": "mock1",
    "date": _d(0),
    "item_ids": ["m_bot1", "m_sho1", "m_top1"],
    "outfit_key": "m_bot1+m_sho1+m_top1",
    "outfit_id": None,
    "posted": False,
    "source": "manual",
}
_STATE = {
    "item_id": "m_top2",
    "status": "laundry",
    "status_since": _d(4),
    "lent_to": None,
    "expected_back": None,
    "note": None,
    "wears_since_wash": 0,
    "reminder": "back_in_closet?",
}
_STATS = {
    **_STATE,
    "item_id": "m_top1",
    "status": "available",
    "reminder": None,
    "wear_count": 12,
    "last_worn": _d(0),
    "first_worn": _d(200),
    "days_since_worn": 0,
    "wears_30d": 4,
    "wears_90d": 9,
}


def _ok(result: dict) -> dict:
    return {"result": result, "mocked": True}


def worn(req: dict) -> dict:
    return _ok({"entry": _ENTRY, "moved_to_laundry": []})


def unworn(req: dict) -> dict:
    return _ok({"removed": True, "entry_id": "mock1"})


def posted(req: dict) -> dict:
    return _ok({"entry": {**_ENTRY, "posted": True}})


def status(req: dict) -> dict:
    return _ok({"items": [_STATE]})


def laundry_done(req: dict) -> dict:
    return _ok({"back_in_closet": ["m_top2"]})


def states(req: dict) -> dict:
    return _ok({"items": [_STATE], "unavailable": ["m_top2"], "reminders": [_STATE]})


def stats(req: dict) -> dict:
    return _ok(
        {
            "items": [
                _STATS,
                {
                    **_STATE,
                    "wear_count": 3,
                    "last_worn": _d(90),
                    "first_worn": _d(300),
                    "days_since_worn": 90,
                    "wears_30d": 0,
                    "wears_90d": 1,
                },
            ],
            "summary": {
                "pieces": 2,
                "worn_30d": 1,
                "utilisation_30d": 0.5,
                "never_worn": [],
                "forgotten_60d": ["m_top2"],
                "most_worn": ["m_top1", "m_top2"],
                "in_laundry": ["m_top2"],
                "lent": [],
                "outfits_logged": 15,
                "repeated_outfits_30d": 1,
            },
            "today": _T.isoformat(),
        }
    )


def history(req: dict) -> dict:
    return _ok({"entries": [_ENTRY, {**_ENTRY, "entry_id": "mock2", "date": _d(3)}]})


def forgotten(req: dict) -> dict:
    return _ok(
        {
            "items": [
                {
                    "item_id": "m_top2",
                    "days_since_worn": 90,
                    "wear_count": 3,
                    "last_worn": _d(90),
                    "status": "laundry",
                }
            ],
            "days": 60,
        }
    )


def recap(req: dict) -> dict:
    return _ok(
        {
            "month": _T.strftime("%Y-%m"),
            "days_logged": 12,
            "wears": 38,
            "distinct_pieces": 17,
            "utilisation": None,
            "top_pieces": [{"item_id": "m_top1", "wears": 4}],
            "first_time_worn": [],
            "repeated_outfits": [{"item_ids": ["m_bot1", "m_sho1", "m_top1"], "times": 2}],
            "posted_looks": 1,
        }
    )
