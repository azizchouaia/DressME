"""Rank challenges for a user: will they join it AND finish it?

ML (default) · models/recommender.json, trained by ml/scripts/train_challenge_recommender.py, which
compares logistic regression, random forest and gradient boosting against the hand formula below
(NDCG@3 by user) and keeps the best. match_score = P(join and finish) for the pair (user, challenge).
  features: feasibility, popularity, affinity, duration / 10, user's smoothed completion rate

if/else fallback (model file missing, or `use_ml=False`) · the hand-written formula used before:
  match = 0.60 × feasibility + 0.25 × popularity + 0.15 × style affinity
  popularity = log(1 + participants) / log(1 + max participants)    (diminishing returns)
  affinity   = Jaccard(challenge tags, user style tags from M5)
"""

import math

from . import mlmodel

MODEL = "recommender.json"


def jaccard(a: set[str], b: set[str]) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def completion_rate(finished: int, joined: int) -> float:
    """Past challenges finished, smoothed so a new user starts at 0.5 (same as in training)."""
    return (finished + 1) / (joined + 2)


def model() -> dict | None:
    try:
        return mlmodel.load(MODEL)
    except FileNotFoundError:
        return None


def run(
    challenges: list[dict],
    user_tags: set[str],
    w=(0.60, 0.25, 0.15),
    user_rate: float = 0.5,
    use_ml: bool = True,
) -> list[dict]:
    """challenges: [{challenge_id, feasibility, participants, tags, duration_days, ...}]
    → sorted by match_score, each with `ranker` ("ml" or "formula")."""
    m = model() if use_ml else None
    top = max((c["participants"] for c in challenges), default=0)
    out = []
    for c in challenges:
        x = {
            "feasibility": c["feasibility"] or 0,
            "popularity": math.log1p(c["participants"]) / math.log1p(top) if top else 0.0,
            "affinity": jaccard(set(c.get("tags", [])), user_tags),
            "duration": c.get("duration_days", 7) / 10,
            "completion_rate": user_rate,
        }
        if m:
            score, ranker = mlmodel.predict_proba(m, x), "ml"
        else:
            score, ranker = w[0] * x["feasibility"] + w[1] * x["popularity"] + w[2] * x["affinity"], "formula"
        out.append({**c, "match_score": round(score, 3), "ranker": ranker})
    return sorted(out, key=lambda c: -c["match_score"])
