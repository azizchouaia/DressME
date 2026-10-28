"""Short memory for one chat: the pose and the clothes still on the avatar."""

_sessions: dict[tuple[str, str], dict] = {}
_counts: dict[tuple[str, str], int] = {}


def recall(user_id: str, session_id: str) -> dict:
    return dict(
        _sessions.get(
            (user_id, session_id),
            {"pose": "stand", "garments": ["shirt", "shorts", "vest"], "question": None},
        )
    )


def remember(user_id: str, session_id: str, pose: str, garments: list[str], question: str | None) -> str:
    key = (user_id, session_id)
    _sessions[key] = {"pose": pose, "garments": list(garments), "question": question}
    _counts[key] = _counts.get(key, 0) + 1
    return f"tryon-{user_id}-{session_id}-{_counts[key]}"
