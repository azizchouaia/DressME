    # M3 · Wear log + item status

    **Owner:** BO1 / BO2 · **Used by:** BO1 BO2 BO3 BO4 BO7

    **Includes:** Worn today log, days since worn, wear counts, status available / laundry / lent

    ## Endpoints (prefix `/m03`)
    - `POST /m03/worn`
- `POST /m03/stats`

    ## Rules
    1. Week 1: ship `mock.py` (fixed data in the agreed shape) so nobody is blocked.
    2. Keep the shapes of `contract.py`; the real `service.py` replaces the mock without changing the API.
    3. Another BO needs a feature here -> they ask the owner, never re-implement it.
