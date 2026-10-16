    # M8 · LLM layer

    **Owner:** BO8 · **Used by:** BO1 BO2 BO3 BO4 BO5 BO6 BO8 BO9

    **Includes:** Request parser (text to JSON), explanation writer (why this outfit), RAG on shops

    ## Endpoints (prefix `/m08`)
    - `POST /m08/parse` — sentence to JSON (weather, season, occasion, size, budget, intent)
    - `POST /m08/explain` — why this outfit
    - `POST /m08/recommend` — rank pieces with the person's tastes
    - `POST /m08/chat` — parse, rank, explain, and retrieve shops in one turn

    Real `service.py` runs when `USE_MOCKS=false`. Piece vectors are passed in the payload (FashionCLIP upstream). A person keeps more than one taste. One extra suggestion is a random step that stays close to those tastes, so later feedback shows whether they move that way.

    Hosted voice (optional, any OpenAI-compatible server): `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`. Leave the key blank in git. Groq example: base `https://api.groq.com/openai/v1`, model `openai/gpt-oss-120b`.

    ## Rules
    1. Week 1: ship `mock.py` (fixed data in the agreed shape) so nobody is blocked.
    2. Keep the shapes of `contract.py`; the real `service.py` replaces the mock without changing the API.
    3. Another BO needs a feature here -> they ask the owner, never re-implement it.
