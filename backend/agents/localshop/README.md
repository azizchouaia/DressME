# LocalShopAgent — owner: M4

Find matching pieces in Tunisian boutiques and brands from the curated shop knowledge base.

## Contract
See `contract.py`. Example input: `tests/fixtures/input.json`.

## Pipeline steps
- `pipeline/retrieve.py` — Hybrid retrieval: multilingual embeddings (bge-m3 / e5) + BM25.
- `pipeline/filter.py` — Price, city, category filters.
- `pipeline/rerank.py` — Re-rank with the user's style vector.
- `pipeline/ingest.py` — Load curated shop CSV/JSON into the index (offline script).

## Run tests
```bash
cd backend && pytest agents/localshop
```

## Status
- [ ] baseline working end-to-end with mocks
- [ ] first real model
- [ ] evaluated (metrics in `ml/notebooks/localshop/`)
