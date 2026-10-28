"""BO7 · helpers shared by the M15 training scripts: the candidate models and their JSON export.

The exported JSON is read by backend/modules/m15_challenges/pipeline/mlmodel.py (plain Python inference).
`check_export` verifies on real samples that the JSON gives the same probabilities as scikit-learn.
"""

import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
from modules.m15_challenges.pipeline import mlmodel  # noqa: E402


def candidates(seed: int = 0) -> dict:
    """The three models compared by every BO7 training script (same data, same metric)."""
    return {
        "logistic_regression": LogisticRegression(max_iter=1000),
        "random_forest": RandomForestClassifier(
            n_estimators=60, max_depth=6, min_samples_leaf=20, random_state=seed, n_jobs=-1
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=150, max_depth=3, learning_rate=0.1, subsample=0.8, random_state=seed
        ),
    }


def _tree(t, leaf_value) -> dict:
    s = t.tree_
    return {
        "left": s.children_left.tolist(),
        "right": s.children_right.tolist(),
        "feature": [int(f) for f in s.feature],
        "threshold": [round(float(v), 6) for v in s.threshold],
        "value": [round(float(leaf_value(v)), 6) for v in s.value],
    }


def export(name: str, model, features: list[str], X_ref: np.ndarray) -> dict:
    if name == "logistic_regression":
        return {
            "model": name,
            "features": features,
            "coef": [round(float(c), 4) for c in model.coef_[0]],
            "intercept": round(float(model.intercept_[0]), 4),
        }
    if name == "random_forest":
        return {
            "model": name,
            "features": features,
            "trees": [_tree(e, lambda v: v[0][1] / v[0].sum()) for e in model.estimators_],
        }
    if name == "gradient_boosting":
        trees = [_tree(e[0], lambda v: v[0][0]) for e in model.estimators_]
        x0 = X_ref[:1]
        boost = sum(e[0].predict(x0)[0] for e in model.estimators_)
        base = float(model.decision_function(x0)[0]) - model.learning_rate * boost
        return {
            "model": name,
            "features": features,
            "base": round(base, 6),
            "learning_rate": model.learning_rate,
            "trees": trees,
        }
    raise ValueError(name)


def check_export(exported: dict, model, X: np.ndarray, n: int = 200) -> float:
    """Largest gap between the JSON inference and scikit-learn on n samples (must be ~0)."""
    feats = exported["features"]
    ref = model.predict_proba(X[:n])[:, 1]
    mine = [mlmodel.predict_proba(exported, dict(zip(feats, row, strict=True))) for row in X[:n]]
    gap = float(np.max(np.abs(ref - np.array(mine))))
    assert gap < 1e-3, f"export mismatch {gap}"
    return gap
