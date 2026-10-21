"""ML · probability that the user completes the challenge.

ml/scripts/train_challenge_completion.py compares logistic regression, random forest and gradient
boosting (5-fold CV AUC) and saves the winner in models/completion.json with the comparison table.
Inference is plain Python (pipeline/mlmodel.py). The if/else part turns the probability into a risk level
used by the nudges and the coach.
"""

from . import mlmodel

MODEL = "completion.json"


def model() -> dict:
    return mlmodel.load(MODEL)


def features(
    feasibility: float, valid_days: int, days_logged: int, streak: int, duration: int, likes: int
) -> dict[str, float]:
    return {
        "feasibility": feasibility,
        "valid_ratio": valid_days / days_logged if days_logged else 0.5,  # neutral prior before day 1
        "streak": streak / duration,
        "progress": days_logged / duration,
        "social": min(1.0, likes / 5),
    }


def predict(x: dict[str, float]) -> float:
    return round(mlmodel.predict_proba(model(), x), 3)


def risk(p: float) -> str:
    if p >= 0.7:
        return "on_track"
    if p >= 0.4:
        return "at_risk"
    return "high_risk"
