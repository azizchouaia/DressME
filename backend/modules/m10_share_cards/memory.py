"""Long-term memory of the share agent (M10): cards, link opens and sign-ups survive a restart.

`SqliteShareStore` = MemoryShareStore + write-through to SQLite (card metadata, opens, sign-ups) and the PNGs
on disk next to the database. Reads stay in RAM, the agent and the API do not change. The referral history it
keeps is what the ambassadors, the best channel and the K-factor are computed from.

Path: env `BO7_SHARE_MEMORY_PATH` (default modules/m10_share_cards/data/memory.sqlite, git-ignored);
":memory:" for tests (nothing on disk, PNGs kept in RAM).
"""

import json
import os
import sqlite3
import threading
from pathlib import Path

from .store import MemoryShareStore

DEFAULT = Path(__file__).resolve().parent / "data" / "memory.sqlite"
SCHEMA = """
CREATE TABLE IF NOT EXISTS card (id TEXT PRIMARY KEY, short_code TEXT, user_id TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS link_open (short_code TEXT, channel TEXT, ts TEXT);
CREATE TABLE IF NOT EXISTS signup (short_code TEXT, new_user_id TEXT PRIMARY KEY, channel TEXT);
"""


class SqliteShareStore(MemoryShareStore):
    def __init__(self, path: str | None = None, use_s3: bool = False):
        super().__init__(use_s3=use_s3)
        path = path or os.environ.get("BO7_SHARE_MEMORY_PATH") or str(DEFAULT)
        self.png_dir = None if path == ":memory:" else Path(path).parent / "cards"
        if self.png_dir:
            self.png_dir.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(path, check_same_thread=False)
        self.con.executescript(SCHEMA)
        self._lock = threading.Lock()
        self._load()

    def _exec(self, sql: str, args: tuple) -> None:
        with self._lock:
            self.con.execute(sql, args)
            self.con.commit()

    def _load(self) -> None:
        for (data,) in self.con.execute("SELECT data FROM card ORDER BY rowid"):
            c = json.loads(data)
            self.cards[c["card_id"]] = c
        self.opens = [{"short_code": s, "channel": c, "ts": t} for s, c, t in
                      self.con.execute("SELECT * FROM link_open ORDER BY rowid")]  # fmt: skip
        self.signups = [{"short_code": s, "new_user_id": u, "channel": c} for s, u, c in
                        self.con.execute("SELECT * FROM signup ORDER BY rowid")]  # fmt: skip

    def save_card(self, meta: dict, png: bytes) -> str:
        url = super().save_card(meta, png)
        c = self.cards[meta["card_id"]]
        if self.png_dir and not self.use_s3:
            (self.png_dir / f"{c['card_id']}.png").write_bytes(png)
        self._exec(
            "INSERT OR REPLACE INTO card VALUES (?, ?, ?, ?)",
            (c["card_id"], c["short_code"], c["user_id"], json.dumps(c, default=str)),
        )
        return url

    def get_png(self, card_id: str) -> bytes | None:
        png = super().get_png(card_id)
        if png is None and self.png_dir:
            f = self.png_dir / f"{card_id}.png"
            png = f.read_bytes() if f.exists() else None
        return png

    def add_open(self, code: str, channel: str = "direct") -> None:
        super().add_open(code, channel)
        o = self.opens[-1]
        self._exec("INSERT INTO link_open VALUES (?, ?, ?)", (o["short_code"], o["channel"], o["ts"]))

    def add_signup(self, code: str, new_user_id: str, channel: str | None = None) -> None:
        before = len(self.signups)
        super().add_signup(code, new_user_id, channel)  # a visit counted with it is saved by add_open
        if len(self.signups) > before:
            s = self.signups[-1]
            row = (s["short_code"], s["new_user_id"], s["channel"])
            self._exec("INSERT OR IGNORE INTO signup VALUES (?, ?, ?)", row)
