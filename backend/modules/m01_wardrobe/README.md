    # M1 · Wardrobe digitiser + item database

    **Owner:** BO3 · **Used by:** BO1 BO2 BO3 BO4 BO5 BO6 BO7 BO8 BO9

    **Includes:** Background removal, classifier (type, colour, season), FashionCLIP embeddings, vector search, duplicate detection, Item table

    ## Endpoints (prefix `/m01`)
    - `POST /m01/classify`
- `POST /m01/similar`
- `POST /m01/items`

    ## Rules
    1. Week 1: ship `mock.py` (fixed data in the agreed shape) so nobody is blocked.
    2. Keep the shapes of `contract.py`; the real `service.py` replaces the mock without changing the API.
    3. Another BO needs a feature here -> they ask the owner, never re-implement it.
