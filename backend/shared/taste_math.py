"""Taste, filters, and outfit assembly on top of a shared embedding space.

The embedder is injected. Production uses FashionCLIP (512-d). Tests pass a
small stand-in so the ranking can be checked without downloading weights.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SLOT_OF = {
    "t-shirt": "top",
    "shirt": "top",
    "top": "top",
    "blouse": "top",
    "jeans": "bottom",
    "pants": "bottom",
    "shorts": "bottom",
    "bottom": "bottom",
    "skirt": "bottom",
    "jacket": "outer",
    "coat": "outer",
    "outer": "outer",
    "shoes": "shoes",
    "sneakers": "shoes",
}
POSITIVE = {"like", "love", "save", "click"}
NEGATIVE = {"dislike", "hate", "skip"}
COLD_WEATHER = {"rain", "rainy", "cold", "wind", "windy", "snow", "snowy", "winter"}


@dataclass
class Conditions:
    weather: str = ""
    season: str = ""
    occasion: str = ""
    size: str = ""
    budget: float | None = None

    def text(self) -> str:
        parts = [self.weather, self.season, self.occasion]
        return " ".join(part.strip() for part in parts if part and part.strip())

    def wants_outer(self) -> bool:
        blob = f"{self.weather} {self.season}".lower()
        return any(word in blob for word in COLD_WEATHER)


@dataclass
class Piece:
    id: str
    name: str
    category: str
    vector: np.ndarray
    size: str | None = None
    price: float | None = None
    stock: int = 1

    @property
    def slot(self) -> str:
        return SLOT_OF.get(self.category.lower(), "other")


@dataclass
class Scored:
    piece: Piece
    score: float
    source: str = "match"


@dataclass
class TasteProfile:
    """Several tastes the person already has, plus one nearby direction to try."""

    tastes: list[np.ndarray]
    members: list[list[str]]
    exploration: np.ndarray | None
    seed: int = 0


@dataclass
class Outfit:
    pieces: list[Scored]
    compatibility: float
    reason: str


@dataclass
class Event:
    kind: str
    piece_id: str
    seconds: float = 0.0
    at: float = 0.0


def unit(vector: np.ndarray) -> np.ndarray:
    array = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(array))
    if norm < 1e-8:
        return array
    return array / norm


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.dot(unit(left), unit(right)))


def average_vectors(vectors: list[np.ndarray]) -> np.ndarray:
    mean = np.mean(np.stack([unit(vector) for vector in vectors], axis=0), axis=0)
    return unit(mean)


class EventLog:
    """One jsonl file per user. Impressions, likes, skips, and watch time."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, user_id: str) -> Path:
        safe = "".join(ch for ch in user_id if ch.isalnum() or ch in "-_") or "user"
        return self.root / f"{safe}.jsonl"

    def append(self, user_id: str, event: Event) -> None:
        if event.at <= 0:
            event.at = time.time()
        line = json.dumps(
            {"kind": event.kind, "piece_id": event.piece_id, "seconds": event.seconds, "at": event.at}
        )
        with self.path(user_id).open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def load(self, user_id: str) -> list[Event]:
        path = self.path(user_id)
        if not path.is_file():
            return []
        events: list[Event] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            events.append(
                Event(
                    kind=raw["kind"],
                    piece_id=raw["piece_id"],
                    seconds=float(raw.get("seconds") or 0),
                    at=float(raw.get("at") or 0),
                )
            )
        return events

    def users(self) -> set[str]:
        return {path.stem for path in self.root.glob("*.jsonl")}


def taste_vector(events: list[Event], vectors: dict[str, np.ndarray]) -> np.ndarray | None:
    """Likes minus dislikes. A newer opinion counts more. Half of the weight is gone after 30 days."""

    stamps = [_stamp(event, events) for event in events]
    newest = max(stamps) if stamps else 0.0
    total: np.ndarray | None = None
    for event, stamp in zip(events, stamps, strict=True):
        vector = vectors.get(event.piece_id)
        if vector is None:
            continue
        if event.kind == "watch":
            sign = 1.0 if event.seconds >= 3 else -1.0
            weight = min(event.seconds / 30.0, 2.0) if sign > 0 else 0.25
        elif event.kind in POSITIVE:
            sign, weight = 1.0, 1.0
        elif event.kind in NEGATIVE:
            sign, weight = -1.0, 1.0
        else:
            continue
        age_days = max(0.0, (newest - stamp) / 86400) if newest else 0.0
        weight *= 0.5 ** (age_days / 30)
        step = unit(vector) * (sign * weight)
        total = step if total is None else total + step
    if total is None:
        return None
    return unit(total)


def _stamp(event: Event, events: list[Event]) -> float:
    if event.at > 0:
        return event.at
    known = [item.at for item in events if item.at > 0]
    return min(known) if known else 0.0


JOIN_TASTE = 0.55
MAX_TASTES = 4
EXPLORE_STEP = 0.45


def _liked_points(events: list[Event], vectors: dict[str, np.ndarray]) -> list[tuple[str, np.ndarray, float]]:
    """Latest positive opinion on each piece, still faded by the 30-day half-life."""

    stamps = [_stamp(event, events) for event in events]
    newest = max(stamps) if stamps else 0.0
    latest: dict[str, tuple[Event, float]] = {}
    for event, stamp in zip(events, stamps, strict=True):
        if event.kind not in POSITIVE and event.kind not in NEGATIVE and event.kind != "watch":
            continue
        previous = latest.get(event.piece_id)
        if previous is None or stamp >= previous[1]:
            latest[event.piece_id] = (event, stamp)
    points: list[tuple[str, np.ndarray, float]] = []
    for piece_id, (event, stamp) in latest.items():
        vector = vectors.get(piece_id)
        if vector is None:
            continue
        if event.kind == "watch":
            if event.seconds < 3:
                continue
            weight = min(event.seconds / 30.0, 2.0)
        elif event.kind in POSITIVE:
            weight = 1.0
        else:
            continue
        age_days = max(0.0, (newest - stamp) / 86400) if newest else 0.0
        weight *= 0.5 ** (age_days / 30)
        if weight <= 0:
            continue
        points.append((piece_id, unit(vector), weight))
    points.sort(key=lambda item: item[2], reverse=True)
    return points


def taste_profile(events: list[Event], vectors: dict[str, np.ndarray], seed: int = 1) -> TasteProfile:
    """Group likes into separate tastes. One extra vector sits close to them, not across the catalogue."""

    clusters: list[list[tuple[str, np.ndarray, float]]] = []
    for piece_id, vector, weight in _liked_points(events, vectors):
        if not clusters:
            clusters.append([(piece_id, vector, weight)])
            continue
        means = [_cluster_mean(group) for group in clusters]
        nearest = max(range(len(clusters)), key=lambda index: cosine(vector, means[index]))
        if cosine(vector, means[nearest]) >= JOIN_TASTE or len(clusters) >= MAX_TASTES:
            clusters[nearest].append((piece_id, vector, weight))
        else:
            clusters.append([(piece_id, vector, weight)])
    tastes = [_cluster_mean(group) for group in clusters]
    members = [[item[0] for item in group] for group in clusters]
    exploration = _exploration(tastes, seed) if tastes else None
    return TasteProfile(tastes=tastes, members=members, exploration=exploration, seed=seed)


def _cluster_mean(group: list[tuple[str, np.ndarray, float]]) -> np.ndarray:
    total = None
    for _piece_id, vector, weight in group:
        step = vector * weight
        total = step if total is None else total + step
    return unit(total)


def _exploration(tastes: list[np.ndarray], seed: int) -> np.ndarray:
    """A stable step sideways from the liked region. Cosine stays high, so the probe is nearby."""

    center = average_vectors(tastes)
    rng = np.random.default_rng(seed)
    noise = unit(rng.normal(size=center.shape).astype(np.float32))
    sideways = noise - float(np.dot(noise, center)) * center
    sideways = unit(sideways)
    return unit(center + EXPLORE_STEP * sideways)


def closest_taste(vector: np.ndarray, tastes: list[np.ndarray]) -> float:
    vector = np.asarray(vector, dtype=np.float32).reshape(-1)
    usable = [taste for taste in tastes if np.asarray(taste).reshape(-1).shape == vector.shape]
    if not usable:
        return 0.0
    return max(cosine(vector, taste) for taste in usable)


def memory_view(events: list[Event], names: dict[str, str]) -> dict[str, list[str]]:
    """The latest opinion on each piece wins, so a later dislike replaces an old like."""

    latest: dict[str, Event] = {}
    for event in events:
        if event.kind not in POSITIVE and event.kind not in NEGATIVE:
            continue
        previous = latest.get(event.piece_id)
        if previous is None or _stamp(event, events) >= _stamp(previous, events):
            latest[event.piece_id] = event
    likes = [names.get(piece_id, piece_id) for piece_id, event in latest.items() if event.kind in POSITIVE]
    dislikes = [names.get(piece_id, piece_id) for piece_id, event in latest.items() if event.kind in NEGATIVE]
    return {"likes": likes, "dislikes": dislikes}


def _size_blocks(want: str, have: str | None) -> bool:
    if not want or not have:
        return False
    left, right = want.strip().lower(), have.strip().lower()
    if left[:1].isdigit() != right[:1].isdigit():
        return False
    return left != right


def allowed(piece: Piece, conditions: Conditions) -> bool:
    if piece.stock <= 0:
        return False
    if conditions.budget is not None and piece.price is not None and piece.price > conditions.budget:
        return False
    return not _size_blocks(conditions.size, piece.size)


def score_piece(
    piece: Piece,
    query: np.ndarray | None,
    taste: np.ndarray | None,
    context: np.ndarray | None,
    tastes: list[np.ndarray] | None = None,
) -> float:
    parts: list[tuple[float, float]] = []
    if query is not None:
        parts.append((0.55, cosine(query, piece.vector)))
    taste_vectors = list(tastes) if tastes else ([] if taste is None else [taste])
    if taste_vectors:
        parts.append((0.25, closest_taste(piece.vector, taste_vectors)))
    if context is not None:
        parts.append((0.20, cosine(context, piece.vector)))
    if not parts:
        return 0.0
    weight = sum(item[0] for item in parts)
    return sum(item[0] * item[1] for item in parts) / weight


def recommend(
    pieces: list[Piece],
    conditions: Conditions,
    query: np.ndarray | None = None,
    taste: np.ndarray | None = None,
    context: np.ndarray | None = None,
    limit: int = 8,
    slot: str | None = None,
    tastes: list[np.ndarray] | None = None,
    exploration: np.ndarray | None = None,
) -> list[Scored]:
    taste_vectors = list(tastes) if tastes else ([] if taste is None else [taste])
    ranked = [
        Scored(piece, score_piece(piece, query, None, context, taste_vectors))
        for piece in pieces
        if allowed(piece, conditions) and (slot is None or piece.slot == slot)
    ]
    ranked.sort(key=lambda item: item.score, reverse=True)
    ranked = ranked[:limit]
    if exploration is None or limit < 1:
        return ranked
    pool = [piece for piece in pieces if allowed(piece, conditions) and (slot is None or piece.slot == slot)]
    if not pool:
        return ranked
    probe = max(pool, key=lambda piece: cosine(piece.vector, exploration))
    if any(item.piece.id == probe.id for item in ranked):
        for item in ranked:
            if item.piece.id == probe.id and closest_taste(probe.vector, taste_vectors) < cosine(probe.vector, exploration):
                item.source = "explore"
        return ranked
    if not ranked:
        return [Scored(probe, cosine(probe.vector, exploration), source="explore")]
    ranked[-1] = Scored(probe, cosine(probe.vector, exploration), source="explore")
    return ranked


def compatibility(pieces: list[Piece]) -> float:
    """Pairwise cosine in the FashionCLIP space.

    FashionCLIP is the pretrained model evaluated on Polyvore outfit
    compatibility. A higher mean similarity means the pieces sit closer
    together in that space.
    """

    if len(pieces) < 2:
        return 1.0
    scores = [
        cosine(pieces[i].vector, pieces[j].vector)
        for i in range(len(pieces))
        for j in range(i + 1, len(pieces))
    ]
    return float(np.mean(scores))


def detect_slot(vector: np.ndarray, prototypes: dict[str, np.ndarray]) -> str:
    return max(prototypes, key=lambda slot: cosine(vector, prototypes[slot]))


def compose(
    pool: list[Piece],
    conditions: Conditions,
    query: np.ndarray | None = None,
    taste: np.ndarray | None = None,
    context: np.ndarray | None = None,
    anchor: Piece | None = None,
    tastes: list[np.ndarray] | None = None,
) -> Outfit:
    slots = ["top", "bottom", "shoes"]
    if conditions.wants_outer():
        slots.append("outer")
    chosen: list[Scored] = []
    used: set[str] = set()
    if anchor is not None and anchor.slot in slots:
        chosen.append(Scored(anchor, 1.0))
        used.add(anchor.id)
        slots = [slot for slot in slots if slot != anchor.slot]
    for slot in slots:
        candidates = recommend(
            pool, conditions, query, taste, context, limit=12, slot=slot, tastes=tastes
        )
        best: Scored | None = None
        best_value = -1e9
        for candidate in candidates:
            if candidate.piece.id in used:
                continue
            partners = [item.piece for item in chosen] + [candidate.piece]
            value = 0.6 * candidate.score + 0.4 * compatibility(partners)
            if value > best_value:
                best, best_value = candidate, value
        if best is not None:
            chosen.append(best)
            used.add(best.piece.id)
    pieces = [item.piece for item in chosen]
    has_taste = bool(tastes) or taste is not None
    reason = _reason(chosen, query is not None, has_taste, conditions)
    return Outfit(pieces=chosen, compatibility=compatibility(pieces), reason=reason)


def _reason(chosen: list[Scored], has_query: bool, has_taste: bool, conditions: Conditions) -> str:
    if not chosen:
        return "The wardrobe has nothing that passes the size, budget, and stock filters."
    names = ", ".join(item.piece.name for item in chosen)
    because: list[str] = []
    if has_query:
        because.append("the photo you sent")
    if has_taste:
        because.append("pieces you have liked")
    if conditions.text():
        because.append(conditions.text())
    if not because:
        return f"{names} is the closest complete outfit in the wardrobe."
    return f"{names} follows {' and '.join(because)}."


def two_tower_status(user_ids: set[str]) -> str:
    """A cross-user model needs many people. Until then each taste vector stays personal."""

    if len(user_ids) < 1000:
        return f"waiting for 1000 users, have {len(user_ids)}"
    return "ready"


@dataclass
class RankerState:
    ready: bool = False
    note: str = "not enough labeled events"
    model: object | None = field(default=None, repr=False)


def maybe_train_ranker(events: list[Event], vectors: dict[str, np.ndarray]) -> RankerState:
    """LightGBM on logged likes and skips. It stays off until there are 40 labels."""

    labels: list[int] = []
    rows: list[list[float]] = []
    for event in events:
        vector = vectors.get(event.piece_id)
        if vector is None:
            continue
        if event.kind in POSITIVE or (event.kind == "watch" and event.seconds >= 3):
            label = 1
        elif event.kind in NEGATIVE or (event.kind == "watch" and event.seconds < 3):
            label = 0
        else:
            continue
        labels.append(label)
        rows.append([float(np.mean(vector)), float(np.std(vector)), float(event.seconds)])
    if len(labels) < 40 or len(set(labels)) < 2:
        return RankerState(note=f"need 40 labeled events with both outcomes, have {len(labels)}")
    try:
        import lightgbm as lgb
    except ImportError:
        return RankerState(note="lightgbm is not installed")
    booster = lgb.LGBMClassifier(n_estimators=40, num_leaves=8, verbose=-1)
    booster.fit(np.asarray(rows, dtype=np.float32), np.asarray(labels))
    return RankerState(ready=True, note="trained on logged feedback", model=booster)
