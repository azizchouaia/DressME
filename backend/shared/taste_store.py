"""One Postgres table for every person's taste memory.

The same FashionCLIP model embeds every photo. Each row belongs to one user.
If Postgres is not reachable, callers keep the local file.
"""

from __future__ import annotations

import json
import os

_ready = False
_down = False

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS taste_memory (
    user_id text NOT NULL,
    piece_id text NOT NULL,
    kind text NOT NULL,
    title text NOT NULL DEFAULT '',
    labels jsonb NOT NULL DEFAULT '[]'::jsonb,
    fit text NOT NULL DEFAULT '',
    gender text NOT NULL DEFAULT '',
    embedding vector(512),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, piece_id)
);
"""


def dsn() -> str:
    raw = os.environ.get("DATABASE_URL", "postgresql://dressme:change_me@localhost:5432/dressme")
    return raw.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg://", "postgresql://")


def connect():
    """Open the taste database, or return None when this machine has no Postgres."""

    global _ready, _down
    if os.environ.get("TASTE_DATA") or _down:
        return None
    try:
        import psycopg
    except ImportError:
        _down = True
        return None
    try:
        conn = psycopg.connect(dsn(), connect_timeout=2)
    except Exception:
        _down = True
        return None
    conn.autocommit = True
    if not _ready:
        conn.execute(SCHEMA)
        _ready = True
    return conn


def save_event(user_id: str, piece_id: str, kind: str, title: str = "", labels=None, fit: str = "", gender: str = "", vector=None) -> bool:
    conn = connect()
    if conn is None:
        return False
    embedding = list(vector) if vector and len(vector) == 512 else None
    with conn:
        conn.execute(
            """
            INSERT INTO taste_memory (user_id, piece_id, kind, title, labels, fit, gender, embedding, updated_at)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, now())
            ON CONFLICT (user_id, piece_id) DO UPDATE SET
                kind = EXCLUDED.kind,
                title = EXCLUDED.title,
                labels = EXCLUDED.labels,
                fit = EXCLUDED.fit,
                gender = EXCLUDED.gender,
                embedding = COALESCE(EXCLUDED.embedding, taste_memory.embedding),
                updated_at = now()
            """,
            (user_id, piece_id, kind, title or piece_id, json.dumps(labels or []), fit or "", gender or "", embedding),
        )
    conn.close()
    return True


def load_events(user_id: str) -> list[dict]:
    conn = connect()
    if conn is None:
        return []
    rows = conn.execute(
        """
        SELECT piece_id, kind, title, labels, fit, gender, embedding::text
        FROM taste_memory
        WHERE user_id = %s
        ORDER BY updated_at
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    events = []
    for piece_id, kind, title, labels, fit, gender, embedding in rows:
        vector = []
        if embedding and embedding.startswith("["):
            vector = [float(part) for part in embedding[1:-1].split(",") if part]
        events.append(
            {
                "id": piece_id,
                "kind": kind,
                "title": title,
                "labels": labels if isinstance(labels, list) else json.loads(labels or "[]"),
                "fit": fit,
                "gender": gender,
                "vector": vector,
            }
        )
    return events
