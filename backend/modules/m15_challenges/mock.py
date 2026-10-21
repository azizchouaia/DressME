"""Week-1 mock of M15: fixed data in the agreed shape. service.py now implements it for real."""

SAMPLE = {
    "challenges": [
        {
            "challenge_id": "ch_7x7",
            "title": "7 days, 7 outfits",
            "description": "Wear a different outfit every day for a week. No piece can be worn twice.",
            "rules": [{"type": "no_repeat", "params": {}}, {"type": "min_items", "params": {"min": 2}}],
            "duration_days": 7,
            "participants": 12,
            "feasibility": 1.0,
        }
    ],
    "progress": None,
    "entry": None,
    "leaderboard": [],
    "posts": [],
}


def challenges(req: dict) -> dict:
    return {"result": SAMPLE, "mocked": True}
