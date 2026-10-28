"""BO7 · M15 · Train the challenge recommender (learning to rank, 3 models vs the hand-written formula).

Question: among the challenges a user can join, which ones will they join AND finish?
Before, M15 ranked challenges with fixed weights: 0.60 × feasibility + 0.25 × popularity + 0.15 × affinity.
Here the ranking is learned: a classifier scores each (user, challenge) pair with P(join and finish),
and the challenges are sorted by that score.

No real users yet, so interactions are simulated with a behaviour model (assumptions in simulate()).
Once the app has data, replace simulate() with the real (user, challenge, finished?) table and retrain;
the features and the saved model format stay the same.

Features of a (user, challenge) pair (all in [0, 1], all available in the app at ranking time):
  feasibility        wardrobe fit of the challenge (M15 feasibility score)
  popularity         log(1 + participants) / log(1 + max participants among the candidates)
  affinity           Jaccard(challenge tags, user style tags from M5)
  duration           duration_days / 10
  completion_rate    user's past challenges finished, smoothed: (finished + 1) / (joined + 2)

Evaluation, by user (test users never seen in training): NDCG@3 and Precision@1 of the ranking,
against the hand-written formula as the baseline. Selection: best NDCG@3 on a validation split of the
training users; the test users give the reported numbers.

Usage:  python ml/scripts/train_challenge_recommender.py
Output: backend/modules/m15_challenges/models/recommender.json (best model + comparison table)
"""

import json
import math
from pathlib import Path

import numpy as np
from bo7_ml_export import candidates, check_export, export

FEATURES = ["feasibility", "popularity", "affinity", "duration", "completion_rate"]
TAGS = [
    "creativity", "rotation", "casual", "minimal", "style_discovery", "tunisian", "heritage",
    "traditional", "sustainability", "capsule", "local",
]  # fmt: skip
HAND_WEIGHTS = (0.60, 0.25, 0.15)  # the formula used before (config.yaml recommend_weights)
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "backend" / "modules" / "m15_challenges" / "models" / "recommender.json"


def sig(x):
    return 1 / (1 + np.exp(-x))


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def simulate(n_users: int = 3000, slate: int = 8, seed: int = 7):
    """Behaviour assumptions:
    - each user has a hidden taste over tags; their M5 style tags are a noisy view of it (2-3 tags);
    - joining is likelier when the challenge matches the taste and is popular (social proof);
    - finishing is likelier with a feasible wardrobe and a reliable user; long challenges hurt
      unreliable users much more than reliable ones (interaction a linear formula cannot express);
    - the past completion rate is a noisy, smoothed view of the hidden reliability (new users: 0.5).
    Returns X (pairs × features), y (joined and finished), groups (user index of each pair)."""
    rng = np.random.default_rng(seed)
    X, y, g = [], [], []
    for u in range(n_users):
        taste = rng.dirichlet(np.full(len(TAGS), 0.4))
        liked = {TAGS[i] for i in np.argsort(-taste)[:3]}
        stated = set(rng.choice(sorted(liked), size=int(rng.integers(1, 3)), replace=False))
        if rng.random() < 0.3:  # profile tags not always right
            stated.add(str(rng.choice(TAGS)))
        reliability = rng.beta(2.5, 2.0)
        joined = int(rng.poisson(3)) if rng.random() > 0.25 else 0
        finished = int(rng.binomial(joined, reliability)) if joined else 0
        rate = (finished + 1) / (joined + 2)
        parts = rng.lognormal(3.0, 1.2, size=slate).astype(int)
        top = parts.max()
        for k in range(slate):
            tags = set(rng.choice(TAGS, size=int(rng.integers(2, 5)), replace=False))
            dur = int(rng.choice([4, 5, 7, 10]))
            feas = float(np.clip(rng.beta(3, 1.6), 0, 1))
            true_aff = sum(taste[TAGS.index(t)] for t in tags)  # hidden
            pop = math.log1p(parts[k]) / math.log1p(top) if top else 0.0
            p_join = sig(-2.2 + 4.5 * true_aff + 1.0 * pop)
            p_finish = sig(-3.0 + 3.2 * feas + 3.4 * reliability - 0.45 * (dur - 4) * (1 - reliability))
            label = int(rng.random() < p_join * p_finish)
            X.append([feas, pop, jaccard(tags, stated), dur / 10, rate])
            y.append(label)
            g.append(u)
    return np.array(X), np.array(y), np.array(g)


def hand_score(X: np.ndarray) -> np.ndarray:
    return X[:, 0] * HAND_WEIGHTS[0] + X[:, 1] * HAND_WEIGHTS[1] + X[:, 2] * HAND_WEIGHTS[2]


def ranking_metrics(scores: np.ndarray, y: np.ndarray, groups: np.ndarray, k: int = 3) -> dict:
    """Mean NDCG@k and Precision@1 over users with at least one positive challenge."""
    ndcg, p1 = [], []
    for u in np.unique(groups):
        m = groups == u
        rel = y[m]
        if rel.sum() == 0:
            continue
        order = np.argsort(-scores[m], kind="stable")
        disc = 1 / np.log2(np.arange(2, k + 2))
        dcg = float((rel[order][:k] * disc[: len(order[:k])]).sum())
        ideal = float((np.sort(rel)[::-1][:k] * disc[: min(k, len(rel))]).sum())
        ndcg.append(dcg / ideal)
        p1.append(float(rel[order][0]))
    return {"ndcg@3": round(float(np.mean(ndcg)), 3), "precision@1": round(float(np.mean(p1)), 3)}


def main() -> None:
    X, y, g = simulate()
    users = np.unique(g)
    rng = np.random.default_rng(0)
    rng.shuffle(users)
    n = len(users)
    tr_u, va_u, te_u = users[: int(0.6 * n)], users[int(0.6 * n) : int(0.8 * n)], users[int(0.8 * n) :]
    tr, va, te = np.isin(g, tr_u), np.isin(g, va_u), np.isin(g, te_u)

    table = {"hand_formula": {"val": ranking_metrics(hand_score(X[va]), y[va], g[va])}}
    table["hand_formula"]["test"] = ranking_metrics(hand_score(X[te]), y[te], g[te])
    fitted = {}
    for name, model in candidates().items():
        model.fit(X[tr], y[tr])
        fitted[name] = model
        table[name] = {
            "val": ranking_metrics(model.predict_proba(X[va])[:, 1], y[va], g[va]),
            "test": ranking_metrics(model.predict_proba(X[te])[:, 1], y[te], g[te]),
        }
    for name, row in table.items():
        print(f"{name:20s} val {row['val']}  test {row['test']}")

    best = max(fitted, key=lambda n: table[n]["val"]["ndcg@3"])
    out = export(best, fitted[best], FEATURES, X[te])
    gap = check_export(out, fitted[best], X[te])
    out["metrics"] = {
        **table[best]["test"],
        "baseline_ndcg@3": table["hand_formula"]["test"]["ndcg@3"],
        "baseline_precision@1": table["hand_formula"]["test"]["precision@1"],
        "n_pairs": int(len(y)),
        "n_users": int(n),
        "positive_rate": round(float(y.mean()), 3),
        "export_max_gap": round(gap, 6),
    }
    out["comparison"] = table
    out["selection"] = "highest NDCG@3 on validation users; test users report the metrics"
    if hasattr(fitted[best], "feature_importances_"):
        imp = fitted[best].feature_importances_
    else:
        imp = np.abs(fitted[best].coef_[0]) / np.abs(fitted[best].coef_[0]).sum()
    out["feature_importance"] = {f: round(float(v), 3) for f, v in zip(FEATURES, imp, strict=True)}
    out["data"] = "simulated (user, challenge) interactions (see simulate()); retrain on real data later"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out))
    m = out["metrics"]
    print(
        f"best: {best} · NDCG@3 {m['ndcg@3']} vs formula {m['baseline_ndcg@3']} · "
        f"P@1 {m['precision@1']} vs {m['baseline_precision@1']} · saved {OUT.relative_to(ROOT)}"
    )


if __name__ == "__main__":
    main()
