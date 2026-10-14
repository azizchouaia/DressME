# M12 · Style evolution tracker

**Owner:** BO4 · **Used by:** BO1 BO3 BO4 BO7 BO8

**Includes:** Monthly style centroid, drift detection, timeline of style changes

## Endpoints (prefix `/m12`)
- `POST /m12/timeline`

## Rules
1. Week 1: ship `mock.py` (fixed data in the agreed shape) so nobody is blocked.
2. Keep the shapes of `contract.py`; the real `service.py` replaces the mock without changing the API.
3. Another BO needs a feature here -> they ask the owner, never re-implement it.
