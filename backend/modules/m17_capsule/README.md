# M17 · Capsule engine

**Owner:** BO1 / BO2 · **Used by:** BO1 BO3 BO4

**Includes:** Pick N pieces that combine the most (greedy / ILP), monthly plan

## Endpoints (prefix `/m17`)
- `POST /m17/capsule`

## Rules
1. Week 1: ship `mock.py` (fixed data in the agreed shape) so nobody is blocked.
2. Keep the shapes of `contract.py`; the real `service.py` replaces the mock without changing the API.
3. Another BO needs a feature here -> they ask the owner, never re-implement it.
