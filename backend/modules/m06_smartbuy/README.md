# M6 · Smart Buy / what-if engine

**Owner:** BO5 · **Used by:** BO1 BO2 BO3 BO5 BO6 BO7 BO8 BO9

**Includes:** Do I own something similar? How many new outfits does it add? Buy / Think / Skip verdict

## Endpoints (prefix `/m06`)
- `POST /m06/verdict`

## Rules
1. Week 1: ship `mock.py` (fixed data in the agreed shape) so nobody is blocked.
2. Keep the shapes of `contract.py`; the real `service.py` replaces the mock without changing the API.
3. Another BO needs a feature here -> they ask the owner, never re-implement it.
