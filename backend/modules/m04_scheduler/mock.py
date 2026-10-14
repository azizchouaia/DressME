"""Mock of M4: fixed data in the real shape. Served while USE_MOCKS=true (or M04_USE_MOCK=true)."""

import datetime as dt

_T = dt.date.today()
_PREFS = {
    "city": "Tunis",
    "timezone": "Africa/Tunis",
    "morning_time": "05:00",
    "notify_time": "07:00",
    "evening_time": "20:00",
    "weekday_occasions": ["work"] * 5 + ["casual"] * 2,
    "jobs": {
        "morning": True,
        "notify": True,
        "evening": True,
        "events": True,
        "weather_tips": True,
        "laundry": True,
        "season": True,
    },
    "push_token": None,
}
_OUTFIT = {
    "outfit_id": "mock1",
    "items": ["m_top1", "m_bot1", "m_sho1"],
    "score": 0.8,
    "explanation": "The pieces work well together.",
}
_ITEMS = {
    "m_top1": {"item_id": "m_top1", "name": "white shirt", "category": "top", "image": None},
    "m_bot1": {"item_id": "m_bot1", "name": "navy pants", "category": "bottom", "image": None},
    "m_sho1": {"item_id": "m_sho1", "name": "brown shoes", "category": "shoes", "image": None},
}


def _ok(result: dict) -> dict:
    return {"result": result, "mocked": True}


def _view(day: dt.date) -> dict:
    return {
        "date": day.isoformat(),
        "kind": "day",
        "occasion": "work",
        "approved": False,
        "choice": 0,
        "options": 3,
        "source": "morning",
        "computed_at": f"{day.isoformat()}T05:00:00",
        "weather": {"temp_c": 18.0, "condition": "clear"},
        "weather_source": "mock",
        "outfit": _OUTFIT,
        "summary": "white shirt + navy pants + brown shoes",
        "items": _ITEMS,
        "context": None,
    }


def _notif(kind: str, title: str, body: str, actions: list[str]) -> dict:
    return {
        "notif_id": f"mock-{kind}",
        "kind": kind,
        "title": title,
        "body": body,
        "data": {"date": _T.isoformat(), "kind": "day"},
        "actions": actions,
        "status": "unread",
        "action_taken": None,
        "delivered": "outbox",
        "created_at": f"{_T.isoformat()}T07:00:00",
    }


def schedule(req: dict) -> dict:
    return _ok(
        {
            "prefs": _PREFS,
            "next_runs": {
                "morning": f"{_T + dt.timedelta(days=1)}T05:00",
                "notify": f"{_T + dt.timedelta(days=1)}T07:00",
                "evening": f"{_T}T20:00",
            },
        }
    )


def calendar(req: dict) -> dict:
    days = [
        {
            "date": (_T + dt.timedelta(days=k)).isoformat(),
            "weekday": "",
            "occasion": "work",
            "occasion_reason": "weekday default",
            "events": [],
            "holidays": [],
            "seasons": [],
            "outfit": None,
            "approved": False,
        }
        for k in range(7)
    ]
    return _ok({"days": days, "upcoming": []})


def event_add(req: dict) -> dict:
    p = req.get("payload") or {}
    return _ok(
        {
            "event": {
                "event_id": "mockevt",
                "date": str(p.get("date", _T)),
                "title": p.get("title", "Event"),
                "occasion": p.get("occasion", "event"),
                "dress_code": None,
                "notes": None,
                "remind_days": 5,
                "kind": "personal",
            }
        }
    )


def event_delete(req: dict) -> dict:
    return _ok({"deleted": True})


def day(req: dict) -> dict:
    return _ok(_view(_T))


def tomorrow(req: dict) -> dict:
    return _ok(_view(_T + dt.timedelta(days=1)))


def approve(req: dict) -> dict:
    return _ok({**_view(_T), "approved": True})


def change(req: dict) -> dict:
    return _ok({**_view(_T), "choice": 1})


def wear(req: dict) -> dict:
    return _ok({**_view(_T), "approved": True, "logged": {"entry": None, "moved_to_laundry": []}})


def week(req: dict) -> dict:
    return _ok({"days": [_view(_T + dt.timedelta(days=k)) for k in range(7)]})


def widget(req: dict) -> dict:
    return _ok(
        {
            "date": _T.isoformat(),
            "temp_c": 18.0,
            "condition": "clear",
            "occasion": "work",
            "summary": "white shirt + navy pants + brown shoes",
            "approved": False,
            "items": list(_ITEMS.values()),
            "deep_link": f"dressme://today?date={_T}",
        }
    )


def notifications(req: dict) -> dict:
    return _ok(
        {
            "notifications": [
                _notif("daily", "Good morning", "Today: white shirt + navy pants · 18°C", ["wear", "change"])
            ],
            "unread": 1,
        }
    )


def notification_action(req: dict) -> dict:
    return _ok({"notif_id": "mock-daily", "status": "acted"})


def run(req: dict) -> dict:
    return _ok({"runs": []})
