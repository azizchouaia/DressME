Trained models of M15 (JSON, read by `pipeline/mlmodel.py`, no scikit-learn needed at runtime).

| File | Task | Trained by |
|---|---|---|
| `completion.json` | P(user finishes the challenge) | `ml/scripts/train_challenge_completion.py` |
| `recommender.json` | P(user joins and finishes) → ranking | `ml/scripts/train_challenge_recommender.py` |

Each file holds the kept model, its test metrics, the comparison of the 3 candidates and the feature importance.
