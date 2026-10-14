    # M8 · LLM layer

    **Owner:** BO8 · **Used by:** BO1 BO2 BO3 BO4 BO5 BO6 BO8 BO9

    **Includes:** Request parser (text to JSON), explanation writer (why this outfit), RAG on shops

    ## Endpoints (prefix `/m08`)
    - `POST /m08/parse`
- `POST /m08/explain`

    ## Rules
    1. Week 1: ship `mock.py` (fixed data in the agreed shape) so nobody is blocked.
    2. Keep the shapes of `contract.py`; the real `service.py` replaces the mock without changing the API.
    3. Another BO needs a feature here -> they ask the owner, never re-implement it.
