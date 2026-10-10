# ProfileAgent — owner: M3

Learn the user's style from feedback events and compute wardrobe analytics (wear rate, duplicates, gaps).

## Contract
See `contract.py`. Example input: `tests/fixtures/input.json`.

## Pipeline steps
- `pipeline/style_vector.py` — EMA of accepted outfit embeddings minus rejected ones.
- `pipeline/bandit.py` — Contextual bandit (LinUCB) re-weighting recommendation features.
- `pipeline/analytics.py` — Wear rate, never-worn items, duplicates (sim > 0.85), gaps.
- `pipeline/cold_start.py` — Initial profile from the onboarding swipe session.

## Run tests
```bash
cd backend && pytest agents/profile
```

## Status
- [ ] baseline working end-to-end with mocks
- [ ] first real model
- [ ] evaluated (metrics in `ml/notebooks/profile/`)
