"""Idea 4 — learn the decision from labelled pieces instead of hand-made weights.

Model: multinomial logistic regression (numpy, L2), features = decide.FEATURES.
Data: the labelled candidates of the current dataset (config 'dataset': synthetic or real).

    python -m modules.m06_smartbuy.learn          # 5-fold comparison rules vs learned, then trains + saves
Then set  decision: learned  in config.yaml.
"""

import asyncio
import json
import random
from pathlib import Path

import numpy as np

from .pipeline.decide import CLASSES, FEATURES, decide, features

MODEL_FILE = Path(__file__).resolve().parent / "models" / "verdict_model.json"


def dataset(agent):
    X, y, facts = [], [], []
    for c in agent.clients.candidates.values():
        f = asyncio.run(agent.facts(c["id"], c.get("user_id", "usr_demo"), c.get("price_tnd", 80)))
        feats = features(f, agent.config)
        X.append([feats[k] for k in FEATURES])
        y.append(CLASSES.index(c["expected"]))
        facts.append(f)
    return np.array(X), np.array(y), facts


def fit(X, y, l2=0.05, lr=0.5, epochs=3000, class_weight=True):
    n, d = X.shape
    k = len(CLASSES)
    W, b = np.zeros((k, d)), np.zeros(k)
    Y = np.eye(k)[y]
    cw = (n / (k * np.maximum(np.bincount(y, minlength=k), 1))) if class_weight else np.ones(k)
    sw = cw[y][:, None]
    for _ in range(epochs):
        z = X @ W.T + b
        z -= z.max(1, keepdims=True)
        p = np.exp(z)
        p /= p.sum(1, keepdims=True)
        g = (p - Y) * sw / n
        W -= lr * (g.T @ X + l2 * W)
        b -= lr * g.sum(0)
    return {"features": FEATURES, "classes": CLASSES, "W": W.round(4).tolist(), "b": b.round(4).tolist(),
            "means": X.mean(0).round(4).tolist()}


def main(folds=5, seed=0):
    from .agent import SmartBuyAgent

    agent = SmartBuyAgent({**SmartBuyAgent().config, "decision": "rules"})
    X, y, facts = dataset(agent)
    idx = list(range(len(y)))
    random.Random(seed).shuffle(idx)
    rules_ok = learned_ok = 0
    for f in range(folds):
        test = idx[f::folds]
        train = [i for i in idx if i not in set(test)]
        m = fit(X[train], y[train])
        for i in test:
            rules_ok += decide(facts[i], agent.config)["verdict"] == CLASSES[y[i]]
            learned_ok += decide(facts[i], agent.config, m)["verdict"] == CLASSES[y[i]]
    n = len(y)
    print(f"{n} labelled pieces ({agent.config.get('dataset')}), {folds}-fold cross-validation")
    print(f"  hand-made rules : {rules_ok / n:.0%}")
    print(f"  learned model   : {learned_ok / n:.0%}")
    m = fit(X, y)
    m["trained_on"] = {"dataset": agent.config.get("dataset"), "n": n, "cv_accuracy": round(learned_ok / n, 3)}
    MODEL_FILE.parent.mkdir(exist_ok=True)
    MODEL_FILE.write_text(json.dumps(m, indent=1))
    print("\nweights (BUY minus SKIP, + pushes toward BUY):")
    W = np.array(m["W"])
    for i, k in enumerate(FEATURES):
        print(f"  {k:12} {W[0, i] - W[2, i]:+.2f}")
    print(f"saved -> {MODEL_FILE}   (set 'decision: learned' in config.yaml to use it)")


if __name__ == "__main__":
    main()
