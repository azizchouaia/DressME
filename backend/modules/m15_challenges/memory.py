"""Memory of the challenges agent (M15).

Three kinds of memory, used together:
  1. Long-term episodic memory · `SqliteChallengeStore`: challenges, participations, daily entries, posts,
     likes and comments are written to SQLite (write-through), so nothing is lost when the server restarts.
     Reads stay in RAM (same methods as MemoryChallengeStore, the agent does not change).
  2. User memory of the coach · `CoachMemory`: per user and challenge, the tips already given (so the RAG
     does not repeat them) and the rules broken again and again (so the coach names the recurring problem).
  3. Short-term (working) memory · `CoachMemory.recall()["recent"]`: the last days of the challenge, given to
     the LLM prompt with today's facts.
The semantic memory is the RAG knowledge base (knowledge/style_tips.yaml), unchanged.

Path: env `BO7_MEMORY_PATH` (default modules/m15_challenges/data/memory.sqlite, git-ignored); ":memory:" for
tests (same code, nothing on disk).
"""

import json
import os
import sqlite3
import threading
from collections import Counter
from pathlib import Path

from .contract import Challenge, Comment, Post
from .store import MemoryChallengeStore

DEFAULT = Path(__file__).resolve().parent / "data" / "memory.sqlite"


def db_path() -> str:
    return os.environ.get("BO7_MEMORY_PATH") or str(DEFAULT)


def connect(path: str | None = None) -> sqlite3.Connection:
    path = path or db_path()
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL") if path != ":memory:" else None
    return con


SCHEMA = """
CREATE TABLE IF NOT EXISTS challenge (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS participation (user_id TEXT, challenge_id TEXT, data TEXT NOT NULL,
  PRIMARY KEY (user_id, challenge_id));
CREATE TABLE IF NOT EXISTS post (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS post_like (post_id TEXT, user_id TEXT, PRIMARY KEY (post_id, user_id));
CREATE TABLE IF NOT EXISTS comment (id TEXT PRIMARY KEY, post_id TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS coach_tip (user_id TEXT, challenge_id TEXT, day INTEGER, tip_id TEXT);
CREATE TABLE IF NOT EXISTS coach_issue (user_id TEXT, challenge_id TEXT, day INTEGER, rule TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS coach_message (user_id TEXT, challenge_id TEXT, day INTEGER, valid INTEGER,
  message TEXT, source TEXT);
"""


class SqliteChallengeStore(MemoryChallengeStore):
    """MemoryChallengeStore + write-through to SQLite: loads everything at start, saves every change."""

    def __init__(self, seed: list[dict] | None = None, con: sqlite3.Connection | None = None):
        self.con = con or connect()
        self._lock = threading.Lock()
        self.con.executescript(SCHEMA)
        super().__init__(seed)  # seed challenges are (re)written, user-created ones are loaded below
        self._load()

    def _exec(self, sql: str, args: tuple = ()) -> None:
        with self._lock:
            self.con.execute(sql, args)
            self.con.commit()

    def _load(self) -> None:
        for (data,) in self.con.execute("SELECT data FROM challenge"):
            ch = Challenge.model_validate_json(data)
            self.challenges.setdefault(ch.challenge_id, ch)
        for u, c, data in self.con.execute("SELECT user_id, challenge_id, data FROM participation"):
            self.participations[(u, c)] = json.loads(data)
        for (data,) in self.con.execute("SELECT data FROM post"):
            p = Post.model_validate_json(data)
            self.posts[p.post_id] = p
            self.likes.setdefault(p.post_id, set())
        for pid, uid in self.con.execute("SELECT post_id, user_id FROM post_like"):
            self.likes.setdefault(pid, set()).add(uid)
        for (data,) in self.con.execute("SELECT data FROM comment ORDER BY rowid"):
            c = Comment.model_validate_json(data)
            self.comments.setdefault(c.post_id, []).append(c)

    def _save_participation(self, user_id: str, challenge_id: str) -> None:
        part = self.participations[(user_id, challenge_id)]
        self._exec(
            "INSERT OR REPLACE INTO participation VALUES (?, ?, ?)",
            (user_id, challenge_id, json.dumps(part, default=str)),
        )

    def _save_post(self, post_id: str) -> None:
        row = (post_id, self.posts[post_id].model_dump_json())
        self._exec("INSERT OR REPLACE INTO post VALUES (?, ?)", row)

    # writes ------------------------------------------------------------------------------------
    def add_challenge(self, ch: Challenge) -> None:
        super().add_challenge(ch)
        if hasattr(self, "con"):
            row = (ch.challenge_id, ch.model_dump_json())
            self._exec("INSERT OR REPLACE INTO challenge VALUES (?, ?)", row)

    def join(self, user_id: str, challenge_id: str) -> dict:
        part = super().join(user_id, challenge_id)
        self._save_participation(user_id, challenge_id)
        return part

    def add_entry(self, user_id: str, challenge_id: str, entry: dict) -> None:
        super().add_entry(user_id, challenge_id, entry)
        self._save_participation(user_id, challenge_id)

    def add_post(self, post: Post) -> None:
        super().add_post(post)
        self._save_post(post.post_id)

    def toggle_like(self, post_id: str, user_id: str) -> int:
        n = super().toggle_like(post_id, user_id)
        if user_id in self.likes[post_id]:
            self._exec("INSERT OR IGNORE INTO post_like VALUES (?, ?)", (post_id, user_id))
        else:
            self._exec("DELETE FROM post_like WHERE post_id = ? AND user_id = ?", (post_id, user_id))
        self._save_post(post_id)
        return n

    def add_comment(self, c: Comment) -> int:
        n = super().add_comment(c)
        row = (c.comment_id, c.post_id, c.model_dump_json())
        self._exec("INSERT OR REPLACE INTO comment VALUES (?, ?, ?)", row)
        self._save_post(c.post_id)
        return n


class CoachMemory:
    """What the coach remembers about a user in a challenge (SQLite, survives restarts)."""

    def __init__(self, con: sqlite3.Connection | None = None, recent_days: int = 3):
        self.con = con or connect()
        self.con.executescript(SCHEMA)
        self.recent_days = recent_days
        self._lock = threading.Lock()

    def recall(self, user_id: str, challenge_id: str) -> dict:
        """{tips_given, issues: {rule: times}, recent: [{day, valid, message}]} for the prompt and the RAG."""
        q = (user_id, challenge_id)
        tips = [t for (t,) in self.con.execute(
            "SELECT tip_id FROM coach_tip WHERE user_id=? AND challenge_id=? ORDER BY day", q)]  # fmt: skip
        issues = Counter(r for (r,) in self.con.execute(
            "SELECT rule FROM coach_issue WHERE user_id=? AND challenge_id=?", q))  # fmt: skip
        recent = [
            {"day": d, "valid": bool(v), "message": m}
            for d, v, m in self.con.execute(
                "SELECT day, valid, message FROM coach_message WHERE user_id=? AND challenge_id=? "
                "ORDER BY day DESC LIMIT ?",
                (*q, self.recent_days),
            )
        ][::-1]
        return {
            "tips_given": tips,
            "issues": dict(issues),  # rule type → times broken before today
            "recent": recent,
        }

    def remember(
        self,
        user_id: str,
        challenge_id: str,
        day: int,
        *,
        valid: bool,
        tip_ids: list[str],
        broken: list[tuple[str, str]],
        message: str,
        source: str,
    ) -> None:
        """broken: [(rule type, violation text)] of today."""
        with self._lock:
            tips = [(user_id, challenge_id, day, t) for t in tip_ids]
            self.con.executemany("INSERT INTO coach_tip VALUES (?, ?, ?, ?)", tips)
            self.con.executemany(
                "INSERT INTO coach_issue VALUES (?, ?, ?, ?, ?)",
                [(user_id, challenge_id, day, r, d) for r, d in broken],
            )
            self.con.execute(
                "INSERT INTO coach_message VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, challenge_id, day, int(valid), message, source),
            )
            self.con.commit()
