"""Stylist memory.

- short-term (conversation): the turns of a chat session, the last ones are replayed to the LLM
- long-term (profile): what the user told about their taste (likes / dislikes / notes), written by the LLM
  through the `remember_preference` tool, injected in every prompt
- episodic: what was worn and what is in the laundry lives in M3 (read through the M3 agent, not copied here)

Plain JSON files under modules/stylist/.data/<user>/ (git-ignored).
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

DATA = Path(os.environ.get("STYLIST_DATA", Path(__file__).parent / ".data"))
MAX_TURNS = 12  # messages replayed to the LLM


def _safe(s: str | None, default: str) -> str:
    return "".join(c for c in (s or default) if c.isalnum() or c in "-_")[:64] or default


def _dir(user: str) -> Path:
    d = DATA / _safe(user, "anonymous")
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------- conversation ----------
def history(user: str, session: str) -> list[dict]:
    f = _dir(user) / f"chat_{_safe(session, 'default')}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def append(user: str, session: str, role: str, content: str) -> None:
    f = _dir(user) / f"chat_{_safe(session, 'default')}.json"
    h = history(user, session)
    h.append({"role": role, "content": content, "at": dt.datetime.now().isoformat(timespec="seconds")})
    f.write_text(json.dumps(h[-200:], ensure_ascii=False, indent=1), encoding="utf-8")


def recent(user: str, session: str) -> list[dict]:
    return [{"role": m["role"], "content": m["content"]} for m in history(user, session)[-MAX_TURNS:]]


# ---------- long-term profile ----------
def profile(user: str) -> dict:
    f = _dir(user) / "profile.json"
    return (
        json.loads(f.read_text(encoding="utf-8"))
        if f.exists()
        else {"likes": [], "dislikes": [], "notes": []}
    )


def remember(user: str, kind: str, value: str) -> dict:
    kind = kind if kind in ("likes", "dislikes", "notes") else "notes"
    value = value.strip()[:120]
    p = profile(user)
    if value and value.lower() not in (v.lower() for v in p[kind]):
        p[kind].append(value)
        other = {"likes": "dislikes", "dislikes": "likes"}.get(kind)
        if other:  # changing one's mind
            p[other] = [v for v in p[other] if v.lower() != value.lower()]
    (_dir(user) / "profile.json").write_text(json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def forget(user: str, session: str | None = None) -> None:
    d = _dir(user)
    for f in d.glob(f"chat_{_safe(session, '*')}.json" if session else "*.json"):
        f.unlink()
