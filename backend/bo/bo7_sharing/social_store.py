"""Owner: BO7 · long-term memory of the BO7 social features (SQLite, write-through like M10 and M15).

Feed posts and their likes / comments, polls and votes, give-aways and requests, follows between users,
and the looks a stylist shared with a client. Path: env `BO7_SOCIAL_PATH` (default
bo/bo7_sharing/data/social.sqlite, git-ignored); ":memory:" in the tests (same code, nothing on disk).
"""

import json
import os
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

DEFAULT = Path(__file__).resolve().parent / "data" / "social.sqlite"
SCHEMA = """
CREATE TABLE IF NOT EXISTS post (post_id TEXT PRIMARY KEY, user_id TEXT, kind TEXT, card_id TEXT, title TEXT,
  caption TEXT, image_url TEXT, share_url TEXT, item_ids TEXT, extra TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS post_like (post_id TEXT, user_id TEXT, PRIMARY KEY (post_id, user_id));
CREATE TABLE IF NOT EXISTS post_comment (comment_id TEXT PRIMARY KEY, post_id TEXT, user_id TEXT, text TEXT,
  created_at TEXT);
CREATE TABLE IF NOT EXISTS poll (poll_id TEXT PRIMARY KEY, user_id TEXT, post_id TEXT, question TEXT,
  candidate TEXT, verdict TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS poll_vote (poll_id TEXT, voter_id TEXT, choice TEXT,
  PRIMARY KEY (poll_id, voter_id));
CREATE TABLE IF NOT EXISTS giveaway (giveaway_id TEXT PRIMARY KEY, user_id TEXT, item_id TEXT, post_id TEXT,
  size TEXT, condition TEXT, city TEXT, note TEXT, status TEXT, given_to TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS giveaway_request (giveaway_id TEXT, user_id TEXT, message TEXT, created_at TEXT,
  PRIMARY KEY (giveaway_id, user_id));
CREATE TABLE IF NOT EXISTS follow (user_id TEXT, target TEXT, PRIMARY KEY (user_id, target));
CREATE TABLE IF NOT EXISTS stylist_share (share_id TEXT PRIMARY KEY, stylist_id TEXT, client_id TEXT,
  card_id TEXT, image_url TEXT, share_url TEXT, item_ids TEXT, note TEXT, created_at TEXT);
"""


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class SocialStore:
    def __init__(self, path: str | None = None):
        path = path or os.environ.get("BO7_SOCIAL_PATH") or str(DEFAULT)
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        self._lock = threading.Lock()

    def _run(self, sql: str, args: tuple = ()) -> None:
        with self._lock:
            self.con.execute(sql, args)
            self.con.commit()

    def _all(self, sql: str, args: tuple = ()) -> list[dict]:
        with self._lock:
            return [dict(r) for r in self.con.execute(sql, args).fetchall()]

    def _one(self, sql: str, args: tuple = ()) -> dict | None:
        rows = self._all(sql, args)
        return rows[0] if rows else None

    # ------------------------------------------------------------------ feed
    def add_post(
        self,
        user_id: str,
        kind: str,
        card: dict,
        item_ids: list[str],
        title: str | None,
        extra: dict | None = None,
    ) -> dict:
        post = {
            "post_id": new_id("fp"),
            "user_id": user_id,
            "kind": kind,
            "card_id": card.get("card_id"),
            "title": title,
            "caption": card.get("caption"),
            "image_url": card.get("image_url"),
            "share_url": card.get("share_url"),
            "item_ids": json.dumps(item_ids),
            "extra": json.dumps(extra or {}),
            "created_at": now(),
        }
        self._run(f"INSERT INTO post VALUES ({','.join('?' * len(post))})", tuple(post.values()))
        return self.post(post["post_id"])

    def set_post_extra(self, post_id: str, extra: dict) -> None:
        self._run("UPDATE post SET extra = ? WHERE post_id = ?", (json.dumps(extra), post_id))

    def post(self, post_id: str) -> dict | None:
        p = self._one("SELECT * FROM post WHERE post_id = ?", (post_id,))
        if p:
            p["item_ids"], p["extra"] = json.loads(p["item_ids"]), json.loads(p["extra"])
        return p

    def posts(self) -> list[dict]:
        ids = self._all("SELECT post_id FROM post ORDER BY created_at DESC, rowid DESC")
        return [self.post(r["post_id"]) for r in ids]

    def toggle_like(self, post_id: str, user_id: str) -> int:
        if self._one("SELECT 1 FROM post_like WHERE post_id = ? AND user_id = ?", (post_id, user_id)):
            self._run("DELETE FROM post_like WHERE post_id = ? AND user_id = ?", (post_id, user_id))
        else:
            self._run("INSERT INTO post_like VALUES (?, ?)", (post_id, user_id))
        return self.likes(post_id)

    def likes(self, post_id: str) -> int:
        return self._one("SELECT COUNT(*) AS n FROM post_like WHERE post_id = ?", (post_id,))["n"]

    def liked(self, post_id: str, user_id: str) -> bool:
        return bool(
            self._one("SELECT 1 FROM post_like WHERE post_id = ? AND user_id = ?", (post_id, user_id))
        )

    def add_comment(self, post_id: str, user_id: str, text: str) -> dict:
        c = {
            "comment_id": new_id("fc"),
            "post_id": post_id,
            "user_id": user_id,
            "text": text,
            "created_at": now(),
        }
        self._run("INSERT INTO post_comment VALUES (?, ?, ?, ?, ?)", tuple(c.values()))
        return c

    def comments(self, post_id: str) -> list[dict]:
        return self._all(
            "SELECT * FROM post_comment WHERE post_id = ? ORDER BY created_at, rowid", (post_id,)
        )

    # ------------------------------------------------------------------ polls
    def add_poll(self, user_id: str, question: str, candidate: dict, verdict: dict) -> dict:
        poll = {
            "poll_id": new_id("poll"),
            "user_id": user_id,
            "post_id": None,
            "question": question,
            "candidate": json.dumps(candidate),
            "verdict": json.dumps(verdict),
            "created_at": now(),
        }
        self._run("INSERT INTO poll VALUES (?, ?, ?, ?, ?, ?, ?)", tuple(poll.values()))
        return self.poll(poll["poll_id"])

    def set_poll_post(self, poll_id: str, post_id: str) -> None:
        self._run("UPDATE poll SET post_id = ? WHERE poll_id = ?", (post_id, poll_id))

    def poll(self, poll_id: str) -> dict | None:
        p = self._one("SELECT * FROM poll WHERE poll_id = ?", (poll_id,))
        if not p:
            return None
        p["candidate"], p["verdict"] = json.loads(p["candidate"]), json.loads(p["verdict"])
        votes = self._all("SELECT voter_id, choice FROM poll_vote WHERE poll_id = ?", (poll_id,))
        p["votes"] = {c: sum(1 for v in votes if v["choice"] == c) for c in ("yes", "no")}
        p["voters"] = {v["voter_id"]: v["choice"] for v in votes}
        return p

    def vote(self, poll_id: str, voter_id: str, choice: str) -> None:
        self._run("INSERT OR REPLACE INTO poll_vote VALUES (?, ?, ?)", (poll_id, voter_id, choice))

    # ------------------------------------------------------------------ give-aways
    def add_giveaway(
        self, user_id: str, item_id: str, size: str | None, condition: str, city: str | None, note: str | None
    ) -> dict:
        g = {
            "giveaway_id": new_id("give"),
            "user_id": user_id,
            "item_id": item_id,
            "post_id": None,
            "size": size,
            "condition": condition,
            "city": city,
            "note": note,
            "status": "open",
            "given_to": None,
            "created_at": now(),
        }
        self._run(f"INSERT INTO giveaway VALUES ({','.join('?' * len(g))})", tuple(g.values()))
        return self.giveaway(g["giveaway_id"])

    def giveaway(self, giveaway_id: str) -> dict | None:
        g = self._one("SELECT * FROM giveaway WHERE giveaway_id = ?", (giveaway_id,))
        if g:
            g["requests"] = self._all(
                "SELECT user_id, message, created_at FROM giveaway_request "
                "WHERE giveaway_id = ? ORDER BY rowid",
                (giveaway_id,),
            )
        return g

    def update_giveaway(self, giveaway_id: str, **fields) -> None:
        sets = ", ".join(f"{k} = ?" for k in fields)
        self._run(f"UPDATE giveaway SET {sets} WHERE giveaway_id = ?", (*fields.values(), giveaway_id))

    def request_giveaway(self, giveaway_id: str, user_id: str, message: str | None) -> None:
        self._run(
            "INSERT OR REPLACE INTO giveaway_request VALUES (?, ?, ?, ?)",
            (giveaway_id, user_id, message, now()),
        )

    def given_item_ids(self, user_id: str) -> set[str]:
        rows = self._all("SELECT item_id FROM giveaway WHERE user_id = ?", (user_id,))
        return {r["item_id"] for r in rows}

    # ------------------------------------------------------------------ follows
    def follow(self, user_id: str, target: str, on: bool = True) -> None:
        if on:
            self._run("INSERT OR IGNORE INTO follow VALUES (?, ?)", (user_id, target))
        else:
            self._run("DELETE FROM follow WHERE user_id = ? AND target = ?", (user_id, target))

    def following(self, user_id: str) -> list[str]:
        return [r["target"] for r in self._all("SELECT target FROM follow WHERE user_id = ?", (user_id,))]

    # ------------------------------------------------------------------ stylist → client
    def add_stylist_share(
        self, stylist_id: str, client_id: str, card: dict, item_ids: list[str], note: str | None
    ) -> dict:
        s = {
            "share_id": new_id("sty"),
            "stylist_id": stylist_id,
            "client_id": client_id,
            "card_id": card.get("card_id"),
            "image_url": card.get("image_url"),
            "share_url": card.get("share_url"),
            "item_ids": json.dumps(item_ids),
            "note": note,
            "created_at": now(),
        }
        self._run(f"INSERT INTO stylist_share VALUES ({','.join('?' * len(s))})", tuple(s.values()))
        return {**s, "item_ids": item_ids}

    def inbox(self, client_id: str) -> list[dict]:
        rows = self._all(
            "SELECT * FROM stylist_share WHERE client_id = ? ORDER BY created_at DESC, rowid DESC",
            (client_id,),
        )
        for r in rows:
            r["item_ids"] = json.loads(r["item_ids"])
        return rows


_store: SocialStore | None = None


def store() -> SocialStore:
    global _store
    if _store is None:
        _store = SocialStore()
    return _store
