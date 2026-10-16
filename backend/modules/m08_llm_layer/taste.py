"""Several tastes per person, plus one nearby direction used as a probe.

Other modules pass the piece vectors (FashionCLIP in production). This file
only clusters and scores them.
"""

from __future__ import annotations

import math
import random

JOIN_TASTE = 0.55
MAX_TASTES = 4
EXPLORE_STEP = 0.45
POSITIVE = {"like", "love", "save", "click"}
NEGATIVE = {"dislike", "hate", "skip"}


def unit(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm < 1e-8:
        return list(vector)
    return [value / norm for value in vector]


def cosine(left: list[float], right: list[float]) -> float:
    a, b = unit(left), unit(right)
    return sum(x * y for x, y in zip(a, b, strict=True))


def average(vectors: list[list[float]]) -> list[float]:
    width = len(vectors[0])
    total = [0.0] * width
    for vector in vectors:
        for index, value in enumerate(unit(vector)):
            total[index] += value
    return unit([value / len(vectors) for value in total])


def _stamp(event: dict, events: list[dict]) -> float:
    at = float(event.get("at") or 0)
    if at > 0:
        return at
    known = [float(item.get("at") or 0) for item in events if float(item.get("at") or 0) > 0]
    return min(known) if known else 0.0


def liked_points(events: list[dict], vectors: dict[str, list[float]]) -> list[tuple[str, list[float], float]]:
    """Latest positive opinion on each piece. Half the weight is gone after 30 days."""

    stamps = [_stamp(event, events) for event in events]
    newest = max(stamps) if stamps else 0.0
    latest: dict[str, tuple[dict, float]] = {}
    for event, stamp in zip(events, stamps, strict=True):
        kind = str(event.get("kind") or "")
        piece_id = str(event.get("piece_id") or "")
        if kind not in POSITIVE and kind not in NEGATIVE and kind != "watch":
            continue
        previous = latest.get(piece_id)
        if previous is None or stamp >= previous[1]:
            latest[piece_id] = (event, stamp)
    points: list[tuple[str, list[float], float]] = []
    for piece_id, (event, stamp) in latest.items():
        vector = vectors.get(piece_id)
        if vector is None:
            continue
        kind = str(event.get("kind") or "")
        if kind == "watch":
            seconds = float(event.get("seconds") or 0)
            if seconds < 3:
                continue
            weight = min(seconds / 30.0, 2.0)
        elif kind in POSITIVE:
            weight = 1.0
        else:
            continue
        age_days = max(0.0, (newest - stamp) / 86400) if newest else 0.0
        weight *= 0.5 ** (age_days / 30)
        if weight > 0:
            points.append((piece_id, unit(vector), weight))
    points.sort(key=lambda item: item[2], reverse=True)
    return points


def _mean(group: list[tuple[str, list[float], float]]) -> list[float]:
    width = len(group[0][1])
    total = [0.0] * width
    for _piece_id, vector, weight in group:
        for index, value in enumerate(vector):
            total[index] += value * weight
    return unit(total)


def exploration_vector(tastes: list[list[float]], seed: int) -> list[float]:
    """One random step sideways from the liked region. It stays close on purpose."""

    center = average(tastes)
    rng = random.Random(seed)
    noise = unit([rng.gauss(0, 1) for _ in center])
    along = sum(x * y for x, y in zip(noise, center, strict=True))
    sideways = unit([value - along * center[index] for index, value in enumerate(noise)])
    return unit([center[index] + EXPLORE_STEP * sideways[index] for index in range(len(center))])


def taste_profile(events: list[dict], vectors: dict[str, list[float]], seed: int = 1) -> dict:
    clusters: list[list[tuple[str, list[float], float]]] = []
    for piece_id, vector, weight in liked_points(events, vectors):
        if not clusters:
            clusters.append([(piece_id, vector, weight)])
            continue
        means = [_mean(group) for group in clusters]
        nearest = max(range(len(clusters)), key=lambda index: cosine(vector, means[index]))
        if cosine(vector, means[nearest]) >= JOIN_TASTE or len(clusters) >= MAX_TASTES:
            clusters[nearest].append((piece_id, vector, weight))
        else:
            clusters.append([(piece_id, vector, weight)])
    tastes = [_mean(group) for group in clusters]
    members = [[item[0] for item in group] for group in clusters]
    exploration = exploration_vector(tastes, seed) if tastes else None
    return {"tastes": tastes, "members": members, "exploration": exploration, "seed": seed}


def closest(vector: list[float], tastes: list[list[float]]) -> float:
    if not tastes:
        return 0.0
    return max(cosine(vector, taste) for taste in tastes)
