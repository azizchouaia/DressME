"""The two trained ML models of M15 (completion, recommender) and their plain-Python inference."""

from modules.m15_challenges.agent import ChallengesAgent
from modules.m15_challenges.pipeline import completion, mlmodel, recommend

TREE = {  # x0 <= 0.5 → 1.0 else 3.0
    "left": [1, -1, -1],
    "right": [2, -1, -1],
    "feature": [0, -2, -2],
    "threshold": [0.5, -2.0, -2.0],
    "value": [0.0, 1.0, 3.0],
}


def test_inference_of_the_three_model_types():
    lr = {"model": "logistic_regression", "features": ["a"], "coef": [2.0], "intercept": -1.0}
    assert abs(mlmodel.predict_proba(lr, {"a": 0.5}) - 0.5) < 1e-9
    rf = {"model": "random_forest", "features": ["a"], "trees": [TREE, TREE]}
    assert mlmodel.predict_proba(rf, {"a": 0.2}) == 1.0  # leaf value is already a probability
    gb = {"model": "gradient_boosting", "features": ["a"], "base": 0.0, "learning_rate": 0.5, "trees": [TREE]}
    low, high = mlmodel.predict_proba(gb, {"a": 0.2}), mlmodel.predict_proba(gb, {"a": 0.9})
    assert 0.5 < low < high < 1


def test_completion_kept_the_best_of_three_models():
    m = completion.model()
    assert set(m["comparison"]) == {"logistic_regression", "random_forest", "gradient_boosting"}
    best = max(m["comparison"], key=lambda n: m["comparison"][n]["cv_auc"])
    assert m["model"] == best
    assert m["metrics"]["auc"] >= m["comparison"]["logistic_regression"]["test_auc"]
    assert m["metrics"]["export_max_gap"] < 1e-3  # JSON inference == scikit-learn


def test_recommender_beats_the_old_formula():
    m = recommend.model()
    assert m["features"] == ["feasibility", "popularity", "affinity", "duration", "completion_rate"]
    assert m["metrics"]["ndcg@3"] > m["metrics"]["baseline_ndcg@3"]
    assert m["metrics"]["precision@1"] > m["metrics"]["baseline_precision@1"]
    assert "hand_formula" in m["comparison"]


CH = [
    {"challenge_id": "easy", "feasibility": 1.0, "participants": 5, "tags": ["minimal"], "duration_days": 5},
    {"challenge_id": "hard", "feasibility": 0.2, "participants": 5, "tags": [], "duration_days": 10},
]


def test_ml_ranker_and_formula_fallback():
    ml = recommend.run(CH, {"minimal"})
    assert ml[0]["challenge_id"] == "easy" and ml[0]["ranker"] == "ml"
    assert 0 <= ml[1]["match_score"] < ml[0]["match_score"] <= 1
    rule = recommend.run(CH, {"minimal"}, use_ml=False)
    assert rule[0]["ranker"] == "formula" and rule[0]["match_score"] == 0.6 + 0.25 + 0.15


def test_reliable_users_get_higher_scores():
    new = recommend.run(CH, {"minimal"}, user_rate=0.5)[0]["match_score"]
    reliable = recommend.run(CH, {"minimal"}, user_rate=0.9)[0]["match_score"]
    assert reliable > new
    assert recommend.completion_rate(0, 0) == 0.5


async def test_agent_recommend_uses_the_ml_ranker():
    agent = ChallengesAgent()
    out = await agent({"user_id": "amen", "action": "recommend"})
    scores = [c["match_score"] for c in out["challenges"]]
    assert scores == sorted(scores, reverse=True)
    assert {c["ranker"] for c in out["challenges"]} == {"ml"}
    assert agent.user_completion_rate("amen") == 0.5
