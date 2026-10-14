    # M5 · Adaptive style profile

    **Owner:** BO4 · **Used by:** BO1 BO2 BO4 BO6 BO8 BO9

    **Includes:** Contextual bandit, style embedding, feedback API (accept / reject / like)

    ## Endpoints (prefix `/m05`)
    - `POST /m05/profile`
- `POST /m05/feedback`
- `POST /m05/gaps`

    ## Rules
    1. Week 1: ship `mock.py` (fixed data in the agreed shape) so nobody is blocked.
    2. Keep the shapes of `contract.py`; the real `service.py` replaces the mock without changing the API.
    3. Another BO needs a feature here -> they ask the owner, never re-implement it.
