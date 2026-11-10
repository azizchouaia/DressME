"""Saved assistant conversations, per user: one JSON file per user in ml/data/chat_history/ (swap for the DB later).

Each conversation = {id, title, updated, messages: [{role, text, agent, cards, trace, question, time}]}.
"""

from __future__ import annotations

import json
import re
import threading
import time
from pathlib import Path

DIR = Path(__file__).resolve().parents[2] / "ml" / "data" / "chat_history"
_LOCK = threading.Lock()
MAX_CONVERSATIONS = 50
MAX_MESSAGES = 200


def _file(user_id: str) -> Path:
    return DIR / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', user_id or 'anon')}.json"


def _load(user_id: str) -> dict:
    try:
        return json.loads(_file(user_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(user_id: str, data: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    keep = sorted(data.values(), key=lambda c: c.get("updated", 0), reverse=True)[:MAX_CONVERSATIONS]
    _file(user_id).write_text(json.dumps({c["id"]: c for c in keep}, ensure_ascii=False), encoding="utf-8")


def add_turn(user_id: str, session_id: str, user_text: str, out: dict) -> None:
    """Save one turn (the user's message + the assistant's answer). Never breaks the chat."""
    try:
        with _LOCK:
            data = _load(user_id)
            now = time.time()
            conv = data.get(session_id) or {"id": session_id, "title": user_text[:60] or "Photo", "messages": []}
            conv["messages"] += [
                {"role": "user", "text": user_text, "time": now},
                {"role": "assistant", "text": out.get("question") or out.get("reply") or "", "agent": out.get("last_agent"),
                 "question": bool(out.get("question")), "cards": out.get("cards") or [], "trace": out.get("trace") or [],
                 "actions": out.get("next_actions") or [], "time": now},
            ]
            conv["messages"] = conv["messages"][-MAX_MESSAGES:]
            conv["updated"] = now
            data[session_id] = conv
            _save(user_id, data)
    except Exception:  # noqa: BLE001
        pass


def conversations(user_id: str) -> list[dict]:
    rows = sorted(_load(user_id).values(), key=lambda c: c.get("updated", 0), reverse=True)
    return [{"id": c["id"], "title": c.get("title"), "updated": c.get("updated"), "count": len(c.get("messages") or []) // 2}
            for c in rows]


def conversation(user_id: str, session_id: str) -> dict | None:
    return _load(user_id).get(session_id)


def delete(user_id: str, session_id: str) -> bool:
    with _LOCK:
        data = _load(user_id)
        if data.pop(session_id, None) is None:
            return False
        _save(user_id, data)
        return True
