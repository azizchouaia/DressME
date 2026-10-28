"""BO7 · M15 · Train the challenge-completion model (3 models compared, the best one is kept).

Question: given how a user is doing in a challenge so far, how likely is it they finish it?
(≥ 80 % of the days valid). The app uses the probability to nudge users at risk (coach message,
easier challenge suggestion).

No real users yet, so participations are simulated with a behaviour model (assumptions written below);
once the app has data, replace `simulate()` with the real participation table and retrain: the features
and the saved model format stay the same.

Features (all in [0, 1]):
  feasibility   wardrobe fit of the challenge (M15 feasibility score)
  valid_ratio   valid days / logged days so far
  streak        current streak / duration
  progress      logged days / duration
  social        likes received, normalised (min(1, likes / 5))

Models compared on the same split: logistic regression, random forest, gradient boosting.
Selection: highest 5-fold cross-validated AUC on the training set; the test set (25 %, never used to
choose) gives the reported metrics. The winner is exported to JSON (see bo7_ml_export.py).

Usage:  python ml/scripts/train_challenge_completion.py
Output: backend/modules/m15_challenges/models/completion.json (best model + comparison table)
"""

import json
import math
from pathlib import Path

import numpy as np
from bo7_ml_export import candidates, check_export, export
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import cross_val_score, train_test_split

FEATURES = ["feasibility", "valid_ratio", "streak", "progress", "social"]
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "backend" / "modules" / "m15_challenges" / "models" / "completion.json"
OLD = OUT.with_name("completion_lr.json")


def sig(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def simulate(n: int = 6000, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Behaviour assumptions: a valid day is likelier with a feasible wardrobe and a motivated user;
    users drop out more after consecutive invalid days and less when friends like their posts."""
    rng = np.random.default_rng(seed)
    X, y = [], []
    for _ in range(n):
        D = int(rng.choice([4, 5, 7, 10]))
        f = rng.uniform(0.2, 1.0)  # feasibility
        m = rng.normal(0, 1)  # motivation (hidden)
        s = rng.uniform(0, 1)  # how social the user's network is (hidden)
        days, likes, bad_run = [], 0, 0
        for _d in range(D):
            if rng.random() < sig(-3.2 - 0.9 * m + 1.3 * bad_run - 0.5 * min(likes, 5) / 5):
                break  # drop-out
            ok = rng.random() < sig(-1.6 + 3.6 * f + 0.6 * m)
            days.append(ok)
            bad_run = 0 if ok else bad_run + 1
            likes += rng.poisson(1.8 * s) if ok else 0
        label = int(sum(days) >= math.ceil(0.8 * D))
        if len(days) < 1:
            continue
        cut = int(rng.integers(1, len(days) + 1))  # snapshot after `cut` logged days
        sub = days[:cut]
        streak = 0
        for ok in reversed(sub):
            if not ok:
                break
            streak += 1
        like_at_cut = likes * cut / max(1, len(days))
        X.append([f, sum(sub) / cut, streak / D, cut / D, min(1.0, like_at_cut / 5)])
        y.append(label)
    return np.array(X), np.array(y)


def main() -> None:
    X, y = simulate()
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.25, random_state=0, stratify=y)
    base = max(yte.mean(), 1 - yte.mean())
    table, fitted = {}, {}
    for name, model in candidates().items():
        cv = cross_val_score(model, Xtr, ytr, cv=5, scoring="roc_auc")
        model.fit(Xtr, ytr)
        p = model.predict_proba(Xte)[:, 1]
        fitted[name] = model
        table[name] = {
            "cv_auc": round(float(cv.mean()), 3),
            "test_auc": round(float(roc_auc_score(yte, p)), 3),
            "test_accuracy": round(float(accuracy_score(yte, p > 0.5)), 3),
            "brier": round(float(brier_score_loss(yte, p)), 4),
        }
        print(f"{name:20s} {table[name]}")
    best = max(table, key=lambda n: table[n]["cv_auc"])
    out = export(best, fitted[best], FEATURES, Xte)
    gap = check_export(out, fitted[best], Xte)
    out["metrics"] = {
        "auc": table[best]["test_auc"],
        "accuracy": table[best]["test_accuracy"],
        "baseline_accuracy": round(float(base), 3),
        "n_train": int(len(ytr)),
        "n_test": int(len(yte)),
        "positive_rate": round(float(y.mean()), 3),
        "export_max_gap": round(gap, 6),
    }
    out["comparison"] = table
    out["selection"] = "highest 5-fold CV AUC on the training set"
    if hasattr(fitted[best], "feature_importances_"):
        imp = fitted[best].feature_importances_
    else:
        imp = np.abs(fitted[best].coef_[0]) / np.abs(fitted[best].coef_[0]).sum()
    out["feature_importance"] = {f: round(float(v), 3) for f, v in zip(FEATURES, imp, strict=True)}
    out["data"] = "simulated participations (see simulate() assumptions); retrain on real data later"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out))
    OLD.unlink(missing_ok=True)
    print(f"best: {best} · test AUC {out['metrics']['auc']} · saved {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
