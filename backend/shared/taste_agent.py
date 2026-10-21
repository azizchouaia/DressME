"""Shared taste model for the deck, outfit recommendations, and buy decisions.

Swipes in the feed and calls from other agents read and write the same
preference file. A like moves the person's tastes. The next ranking follows.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

from shared.taste_math import SLOT_OF, Conditions, Event, Piece, closest_taste, compose, recommend, taste_profile

ROOT = Path(__file__).resolve().parents[2] / "feed" / "server" / "data"


def data_root() -> Path:
    override = os.environ.get("TASTE_DATA")
    return Path(override) if override else ROOT


def _users_path() -> Path:
    return data_root() / "users.json"


def _vectors_path() -> Path:
    return data_root() / "vectors.json"


def _read(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _state(user_id: str) -> tuple[dict, dict]:
    users = _read(_users_path())
    state = users.setdefault(user_id, {"like": {}, "skip": [], "dislike": [], "save": {}, "profile": ""})
    state.setdefault("like", {})
    state.setdefault("skip", [])
    state.setdefault("dislike", [])
    state.setdefault("save", {})
    state.setdefault("profile", "")
    state.setdefault("avoid", {})
    return users, state


def _vector_for(piece_id: str, state: dict, cache: dict, supplied) -> list | None:
    if supplied:
        return list(supplied)
    liked = (state.get("like") or {}).get(piece_id) or {}
    if isinstance(liked, dict) and liked.get("vector"):
        return liked["vector"]
    known = cache.get(piece_id) or {}
    return known.get("vector")


def learn(user_id: str, piece_id: str, kind: str, vector=None, title: str = "", labels=None, fit: str = "", gender: str = "") -> dict:
    """Record a preference. like, save, and dislike all change the next ranking."""

    if kind not in {"like", "save", "dislike", "skip"} or not piece_id:
        raise ValueError("kind must be like, save, dislike, or skip")
    users, state = _state(user_id)
    cache = _read(_vectors_path())
    stored = _vector_for(piece_id, state, cache, vector)
    if stored:
        cache[piece_id] = {
            "vector": stored,
            "labels": labels or [],
            "fit": fit,
            "gender": gender,
        }
        _write(_vectors_path(), cache)
    if kind == "like":
        state["like"][piece_id] = {
            "title": title or piece_id,
            "labels": labels or [],
            "fit": fit,
            "gender": gender,
            "vector": stored or [],
        }
    elif kind == "save":
        state["save"][piece_id] = {"title": title or piece_id, "labels": labels or [], "fit": fit, "gender": gender}
        if stored:
            state["like"][piece_id] = {
                "title": title or piece_id,
                "labels": labels or [],
                "fit": fit,
                "gender": gender,
                "vector": stored,
            }
    else:
        bucket = state[kind]
        if piece_id not in bucket:
            bucket.append(piece_id)
        if kind == "dislike" and title:
            state.setdefault("avoid", {})[piece_id] = title
    _write(_users_path(), users)
    from shared.taste_store import save_event

    save_event(user_id, piece_id, kind, title=title, labels=labels or [], fit=fit, gender=gender, vector=stored)
    return {"user_id": user_id, "id": piece_id, "kind": kind, "adapted": True}


def _from_postgres(user_id: str):
    from shared.taste_store import load_events

    rows = load_events(user_id)
    if not rows:
        return None
    vectors: dict[str, np.ndarray] = {}
    events: list[Event] = []
    disliked: set[str] = set()
    state = {"like": {}, "skip": [], "dislike": [], "save": {}, "profile": ""}
    for row in rows:
        if row["kind"] == "dislike":
            disliked.add(row["id"])
            state["dislike"].append(row["id"])
        elif row["kind"] == "skip":
            state["skip"].append(row["id"])
        elif row["kind"] == "save":
            state["save"][row["id"]] = row
        if row["kind"] == "dislike" and row.get("title"):
            state.setdefault("avoid", {})[row["id"]] = row["title"]
        if row["kind"] == "like" and isinstance(row.get("vector"), list) and len(row["vector"]) == 512:
            vectors[row["id"]] = np.asarray(row["vector"], dtype=np.float32)
            events.append(Event(kind="like", piece_id=row["id"], at=1))
            state["like"][row["id"]] = row
    return state, {}, events, vectors, disliked


def _memory(user_id: str):
    stored = _from_postgres(user_id)
    if stored is not None:
        return stored
    users, state = _state(user_id)
    cache = _read(_vectors_path())
    vectors: dict[str, np.ndarray] = {}
    events: list[Event] = []
    for piece_id, value in (state.get("like") or {}).items():
        raw = value.get("vector") if isinstance(value, dict) else None
        raw = raw or (cache.get(piece_id) or {}).get("vector")
        if not isinstance(raw, list) or len(raw) != 512:
            continue
        vectors[piece_id] = np.asarray(raw, dtype=np.float32)
        events.append(Event(kind="like", piece_id=piece_id, at=1))
    disliked = set(state.get("dislike") or [])
    return state, cache, events, vectors, disliked


def _category(item: dict) -> str:
    for label in [item.get("category") or "", *(item.get("labels") or [])]:
        if str(label).lower() in SLOT_OF:
            return str(label).lower()
    return "other"


def _pieces(candidates: list[dict], cache: dict, known: dict[str, np.ndarray]) -> list[Piece]:
    pieces = []
    for item in candidates:
        piece_id = item.get("id")
        if not piece_id:
            continue
        raw = item.get("vector") or (known.get(piece_id).tolist() if piece_id in known else None)
        raw = raw or (cache.get(piece_id) or {}).get("vector")
        if not raw:
            continue
        pieces.append(
            Piece(
                id=piece_id,
                name=item.get("title") or piece_id,
                category=_category(item),
                vector=np.asarray(raw, dtype=np.float32),
                price=item.get("price"),
            )
        )
    return pieces


def _scored(item: Scored) -> dict:
    return {
        "id": item.piece.id,
        "title": item.piece.name,
        "score": int(round(min(1.0, max(0.0, item.score)) * 100)),
        "source": item.source,
    }


def score_map(user_id: str, items: list[dict]) -> dict[str, int]:
    """0–100 match against the tastes this person has already shown."""

    _state_ignored, cache, events, vectors, disliked = _memory(user_id)
    profile = taste_profile(events, vectors) if events else None
    scores = {}
    for item in items:
        piece_id = item.get("id")
        if not piece_id or piece_id in disliked:
            scores[piece_id] = 0
            continue
        raw = item.get("vector") or (vectors.get(piece_id).tolist() if piece_id in vectors else None)
        raw = raw or (cache.get(piece_id) or {}).get("vector")
        if not raw or profile is None or not profile.tastes:
            scores[piece_id] = 0
            continue
        scores[piece_id] = int(round(min(1.0, max(0.0, closest_taste(np.asarray(raw, dtype=np.float32), profile.tastes))) * 100))
    return scores


def advise(user_id: str, candidates: list[dict] | None = None, purpose: str = "outfit", limit: int = 8) -> dict:
    """Rank pieces for an outfit or a purchase using the same tastes as the deck."""

    _state, cache, events, vectors, disliked = _memory(user_id)
    profile = taste_profile(events, vectors) if events else None
    tastes = profile.tastes if profile else []
    pieces = [piece for piece in _pieces(candidates or [], cache, vectors) if piece.id not in disliked]
    budget = None
    for item in candidates or []:
        if item.get("budget") is not None:
            budget = float(item["budget"])
            break
    conditions = Conditions(budget=budget)
    if purpose == "outfit" and pieces:
        outfit = compose(pieces, conditions, tastes=tastes or None)
        items = [_scored(item) for item in outfit.pieces]
        score = int(round(min(1.0, max(0.0, outfit.compatibility)) * 100)) if items else 0
    else:
        ranked = recommend(
            pieces,
            conditions,
            tastes=tastes or None,
            exploration=profile.exploration if profile else None,
            limit=limit,
        ) if pieces else []
        items = [_scored(item) for item in ranked]
        score = items[0]["score"] if items else 0
    return {
        "purpose": "buy" if purpose == "buy" else "outfit",
        "adapted": bool(tastes),
        "tastes": len(tastes),
        "score": score,
        "verdict": "buy" if purpose == "buy" and score >= 55 else ("skip" if purpose == "buy" else "wear"),
        "items": items,
        "next_actions": [],
    }


def brief(user_id: str) -> dict:
    """What this person loves, avoids, and has saved. Scores stay with score_map."""

    state, _cache, _events, _vectors, _disliked = _memory(user_id)
    loves = [value["title"] for value in (state.get("like") or {}).values() if isinstance(value, dict) and value.get("title")]
    wardrobe = [value["title"] for value in (state.get("save") or {}).values() if isinstance(value, dict) and value.get("title")]
    avoids = [title for title in (state.get("avoid") or {}).values() if title]
    return {
        "gender": state.get("profile") or "",
        "loves": loves[:12],
        "avoids": avoids[:8],
        "wardrobe": wardrobe[:12],
    }
