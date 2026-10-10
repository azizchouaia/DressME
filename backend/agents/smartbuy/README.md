# SmartBuyAgent — owner: M4

Judge whether a new piece complements or duplicates the user's wardrobe and how many outfits it unlocks.

## Contract
See `contract.py`. Example input: `tests/fixtures/input.json`.

## Pipeline steps
- `pipeline/neighbours.py` — k-NN of the probe embedding in the wardrobe (pgvector / Qdrant).
- `pipeline/redundancy.py` — Duplicate if similarity > threshold.
- `pipeline/unlock.py` — Ask the Stylist agent how many outfits the probe unlocks.
- `pipeline/score.py` — Weighted score: gap fill, compatibility, redundancy penalty.

## Run tests
```bash
cd backend && pytest agents/smartbuy
```

## Status
- [ ] baseline working end-to-end with mocks
- [ ] first real model
- [ ] evaluated (metrics in `ml/notebooks/smartbuy/`)
