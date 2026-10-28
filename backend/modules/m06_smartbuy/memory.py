"""Smart Buy memory, per user. One JSON file per user in ml/data/bo5/memory/ (swap for the DB later).

- short term (session): the last request + the question waiting for an answer -> 'answer' needs no new photo
- long term: past decisions, feedback (bought / liked), the user's fit references and preferences
"""

import json
import time
import uuid
from pathlib import Path

DIR = Path(__file__).resolve().parents[3] / "ml" / "data" / "bo5" / "memory"
MAX_HISTORY = 50


class AgentMemory:
    def __init__(self, folder: Path | None = DIR):
        self.folder = folder
        self._cache: dict[str, dict] = {}

    def _path(self, user_id: str) -> Path | None:
        safe = "".join(ch for ch in user_id if ch.isalnum() or ch in "-_")
        return self.folder / f"{safe}.json" if self.folder else None

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
        m = self.load(user_id)
        did = f"dec_{uuid.uuid4().hex[:10]}"
        m["sessions"][session_id] = {"request": request, "decision_id": did, "question_key": out.get("question_key"),
                                     "question": out.get("question"), "at": time.time()}
        m["history"].insert(0, {"decision_id": did, "piece": out.get("piece"), "verdict": out["verdict"],
                                "score": out["score"], "price_tnd": request.get("price_tnd"), "offset": out.get("threshold_offset", 0),
                                "at": time.strftime("%Y-%m-%d %H:%M"), "feedback": None})
        del m["history"][MAX_HISTORY:]
        if len(m["sessions"]) > 20:  # keep the latest sessions only
            for k in sorted(m["sessions"], key=lambda k: m["sessions"][k]["at"])[:-20]:
                del m["sessions"][k]
        self._save(user_id)
        return did

    def feedback(self, user_id: str, decision_id: str, bought: bool | None, liked: bool | None) -> dict | None:
        m = self.load(user_id)
        for h in m["history"]:
            if h["decision_id"] == decision_id:
                h["feedback"] = {"bought": bought, "liked": liked}
                self._save(user_id)
                return h
        return None

    def history(self, user_id: str, n: int = 10) -> list[dict]:
        return self.load(user_id)["history"][:n]

    def same_piece_before(self, user_id: str, piece: str) -> dict | None:
        return next((h for h in self.load(user_id)["history"] if h.get("piece") == piece), None)

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
