    # M4 · Scheduler, notifications + outfit calendar

    **Owner:** BO1 / BO2 · **Used by:** BO1 BO2 BO6 BO8

    **Includes:** Scheduled jobs (05:00 outfit, 20:00 tomorrow), cache, push notifications, calendar of events / occasions

    ## Endpoints (prefix `/m04`)
    - `POST /m04/schedule`
- `POST /m04/calendar`

    ## Rules
    1. Week 1: ship `mock.py` (fixed data in the agreed shape) so nobody is blocked.
    2. Keep the shapes of `contract.py`; the real `service.py` replaces the mock without changing the API.
    3. Another BO needs a feature here -> they ask the owner, never re-implement it.
