# StylistAgent — owner: M2

Generate ranked outfits from the user's wardrobe for an occasion, the weather and their style.

## Contract
See `contract.py`. Example input: `tests/fixtures/input.json`.

## Pipeline steps
- `pipeline/candidates.py` — Rule-based filtering: season, weather, formality, category slots.
- `pipeline/compatibility.py` — Score combinations (CLIP cosine baseline -> model trained on Polyvore).
- `pipeline/diversify.py` — MMR re-ranking so the k proposals differ.
- `pipeline/explain.py` — Short reasons from scores/attributes (LLM optional).

## Run tests
```bash
cd backend && pytest agents/stylist
```

## Status
- [ ] baseline working end-to-end with mocks
- [ ] first real model
- [ ] evaluated (metrics in `ml/notebooks/stylist/`)
