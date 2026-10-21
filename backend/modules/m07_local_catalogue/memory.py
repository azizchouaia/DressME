"""localshop memory, per user. One JSON file per user in ml/data/bo6/memory/ (swap for the DB later).

- short term (session): the last search request + the question waiting for an answer, so the user can
  answer it ("femme") or ask for more results without repeating the request;
- long term: past searches, feedback (useful / bought) and preferences learned from answers (gender).

A caller without user_id is "anonymous": kept in RAM for its sessions, never written to disk.
"""

import json
import time
import uuid
from pathlib import Path

from .paths import CONFIG, MEMORY_DIR

ANONYMOUS = "anonymous"


def default_folder() -> Path:
    return MEMORY_DIR


class AgentMemory:
    def __init__(self, folder: Path | None = None):
        self.folder = folder or default_folder()
        self._cache: dict[str, dict] = {}

    def _path(self, user_id: str) -> Path | None:
        if not self.folder or user_id == ANONYMOUS:
            return None
        safe = "".join(ch for ch in user_id if ch.isalnum() or ch in "-_")
        return self.folder / f"{safe}.json"

    def load(self, user_id: str) -> dict:
        if user_id not in self._cache:
            p = self._path(user_id)
            data = json.loads(p.read_text(encoding="utf-8")) if p and p.exists() else {}
            data.setdefault("sessions", {})
            data.setdefault("history", [])
            data.setdefault("preferences", {})
            self._cache[user_id] = data
        return self._cache[user_id]

    def _save(self, user_id: str) -> None:
        p = self._path(user_id)
        if p:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(self._cache[user_id], indent=1, ensure_ascii=False), encoding="utf-8")

    # ---- short term
    def session(self, user_id: str, session_id: str) -> dict:
        return self.load(user_id)["sessions"].get(session_id, {})

    # ---- long term
    def remember(self, user_id: str, session_id: str, request: dict, out: dict) -> str:
        """Save the search of this session (request + open question) and add it to the history."""
        m = self.load(user_id)
        did = f"loc_{uuid.uuid4().hex[:10]}"
        m["sessions"][session_id] = {
            "request": request,
            "decision_id": did,
            "question": out.get("question"),
            "question_key": out.get("question_key"),
            "at": time.time(),
        }
        parsed = out.get("parsed") or {}
        m["history"].insert(
            0,
            {
                "decision_id": did,
                "request": " ".join(t for t in (request.get("query"), request.get("gap")) if t) or None,
                "filters": {
                    k: parsed.get(k)
                    for k in ("subcategory", "category", "color", "gender", "city", "max_price_tnd")
                    if parsed.get(k) is not None
                },
                "total_matches": out.get("total_matches", 0),
                "shown": [r["product_id"] for r in out.get("results", [])],
                "at": time.strftime("%Y-%m-%d %H:%M"),
                "feedback": None,
            },
        )
        del m["history"][CONFIG["memory_history"] :]
        keep = CONFIG["memory_sessions"]  # latest conversations only
        for k in sorted(m["sessions"], key=lambda k: m["sessions"][k]["at"])[:-keep]:
            del m["sessions"][k]
        self._save(user_id)
        return did

    def feedback(
        self, user_id: str, decision_id: str, useful: bool | None, bought_product_id: str | None
    ) -> dict | None:
        m = self.load(user_id)
        for h in m["history"]:
            if h["decision_id"] == decision_id:
                h["feedback"] = {"useful": useful, "bought_product_id": bought_product_id}
                self._save(user_id)
                return h
        return None

    def history(self, user_id: str, n: int = 10) -> list[dict]:
        return self.load(user_id)["history"][:n]

    def preferences(self, user_id: str) -> dict:
        return self.load(user_id)["preferences"]

    def set_preferences(self, user_id: str, **prefs) -> dict:
        p = self.load(user_id)["preferences"]
        p.update({k: v for k, v in prefs.items() if v is not None})
        self._save(user_id)
        return p

    def forget(self, user_id: str) -> None:
        self._cache.pop(user_id, None)
        p = self._path(user_id)
        if p and p.exists():
            p.unlink()
