"""ML · inference for the models trained in ml/scripts/ and saved as JSON in models/.

The training scripts compare several scikit-learn models and export the best one to JSON, so the app
runs it with plain Python (no scikit-learn or pickle at runtime, no version lock between training and
serving). Supported exports:
  logistic_regression   sigmoid(intercept + Σ coef·x)
  gradient_boosting     sigmoid(base + learning_rate · Σ tree(x))       (boosted regression trees)
  random_forest         mean over trees of the leaf's positive-class share
A tree is stored as parallel arrays (scikit-learn's tree_ layout): left, right, feature, threshold, value;
a leaf has left == -1.
"""

import json
import math
from functools import lru_cache
from pathlib import Path

MODELS = Path(__file__).resolve().parents[1] / "models"


@lru_cache(maxsize=8)
def load(name: str) -> dict:
    return json.loads((MODELS / name).read_text())


def _sigmoid(z: float) -> float:
    return 1 / (1 + math.exp(-z))


def _tree(t: dict, x: list[float]) -> float:
    node = 0
    while t["left"][node] != -1:
        node = t["left"][node] if x[t["feature"][node]] <= t["threshold"][node] else t["right"][node]
    return t["value"][node]


def predict_proba(m: dict, features: dict[str, float]) -> float:
    """Probability of the positive class for one sample, given as {feature name: value}."""
    x = [float(features[f]) for f in m["features"]]
    kind = m["model"]
    if kind == "logistic_regression":
        return _sigmoid(m["intercept"] + sum(w * v for w, v in zip(m["coef"], x, strict=True)))
    if kind == "gradient_boosting":
        return _sigmoid(m["base"] + m["learning_rate"] * sum(_tree(t, x) for t in m["trees"]))
    if kind == "random_forest":
        return sum(_tree(t, x) for t in m["trees"]) / len(m["trees"])
    raise ValueError(f"unknown model type {kind!r}")
