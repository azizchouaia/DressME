"""Decision layer: facts -> verdict, with 2 interchangeable deciders.

- rules   : hand-made weighted score + thresholds (default, explainable, no data needed)
- learned : multinomial logistic regression trained on labelled pieces (learn.py)

Both expose per-feature contributions (XAI): how much each factor pushed toward BUY (+) or away (-),
compared with an average piece.
"""

import math

from . import score

FEATURES = ["new_outfits", "gap_fill", "novelty", "price_value", "fair_price", "same_type", "duplicate", "goal_fit"]
CLASSES = ["buy", "think", "skip"]
ORDER = {"skip": 0, "think": 1, "buy": 2}
NAMES = {"new_outfits": "new outfits", "gap_fill": "fills a gap", "novelty": "novelty",
         "price_value": "price per outfit", "fair_price": "fair price for this type",
         "same_type": "pieces of same type", "duplicate": "duplicate", "goal_fit": "fits your goals"}


def features(facts: dict, cfg: dict) -> dict:
    sc = score.compute(facts["red"], facts["unl"], facts["gap"], facts["price"], cfg)
    b = sc["breakdown"]
    typ, price = facts.get("typical_price"), facts["price"]
    if typ and price:
        ratio = price / typ
        fair = 1.0 if ratio <= 1 else max(0.0, 1 - (ratio - 1) / 0.6)  # 1.6x the usual price -> 0
    else:
        fair = 0.5
    goal = facts.get("goal", {}).get("score", 0.0)
    sc_goal = max(0, min(100, sc["score"] + round(cfg.get("goal_points", 15) * goal)))
    return {**b, "goal_fit": round((goal + 1) / 2, 2), "_goal": goal, "fair_price": round(fair, 2), "same_type": min(facts["n_same"] / 5, 1.0), "duplicate": 1.0 if facts["red"]["is_duplicate"] else 0.0,
            "_score": sc_goal, "_cpo": sc["cost_per_outfit"]}


def _softmax(z):
    m = max(z)
    e = [math.exp(x - m) for x in z]
    s = sum(e)
    return [x / s for x in e]


def decide(facts: dict, cfg: dict, model: dict | None = None, offset: int = 0) -> dict:
    """offset: personal threshold shift (bandit), + = stricter."""
    f = features(facts, cfg)
    sc = f["_score"]
    if model:
        x = [f[k] for k in model["features"]]
        z = [sum(w * xi for w, xi in zip(model["W"][c], x)) + model["b"][c] for c in range(len(CLASSES))]
        z[0] -= offset / 10  # stricter user -> less BUY
        p = _softmax(z)
        v = CLASSES[max(range(3), key=lambda i: p[i])]
        if facts["red"]["is_duplicate"]:
            v = "skip"  # business rule stays hard
        wb, ws = model["W"][0], model["W"][2]
        contrib = {k: round((wb[i] - ws[i]) * (x[i] - model["means"][i]) * 10, 1) for i, k in enumerate(model["features"])}
        probs = {c: round(p[i], 3) for i, c in enumerate(CLASSES)}
        sc = round(100 * (p[0] + 0.5 * p[1]))  # display score consistent with the model (buy=100, think=50, skip=0)
    else:
        rc = {**cfg, "buy_threshold": cfg["buy_threshold"] + offset, "skip_threshold": cfg["skip_threshold"] + offset}
        v = score.verdict(sc, facts["red"]["is_duplicate"], rc, facts["n_same"])
        w = cfg["weights"]
        mean = cfg.get("feature_means", {})
        contrib = {k: round(100 * w[k] * (f[k] - mean.get(k, 0.5)), 1) for k in w}
        if facts["n_same"] >= cfg.get("max_same_type", 99):
            contrib["same_type"] = -15.0
        if f["_goal"]:
            contrib["goal_fit"] = round(cfg.get("goal_points", 15) * f["_goal"], 1)
        if facts["red"]["is_duplicate"]:
            contrib["duplicate"] = -100.0
        probs = None
    if facts.get("goal", {}).get("over_budget"):
        contrib["over_budget"] = -20.0
    if v == "buy" and facts.get("goal", {}).get("over_budget"):
        v = "think"  # the user's own budget is a hard limit, like owning too many of a type
    return {"verdict": v, "score": sc, "features": {k: f[k] for k in FEATURES}, "breakdown": {k: f[k] for k in
            ("new_outfits", "gap_fill", "novelty", "price_value")}, "cost_per_outfit": f["_cpo"],
            "contributions": contrib, "probabilities": probs}
