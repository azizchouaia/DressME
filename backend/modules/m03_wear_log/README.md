# M3 · Wear log + item status

**Owner:** BO1 / BO2 · **Used by:** BO1 BO2 BO3 BO4 BO7 (and M2)

**Includes:** "Worn today" log, days since worn, wear counts, status available / laundry / lent,
auto-laundry after N wears, "back in your closet?" and lent-overdue reminders, posted looks, monthly recap.

No ML model here: a log and rule-based statistics. M3 does not own the pieces (M1 does); it stores what
happened to item ids.

## Endpoints (prefix `/m03`)
Team envelope `{user_id, payload}` → `{result, mocked}`; payloads are typed in `contract.py`.

| Endpoint | What it does | Payload |
|---|---|---|
| `POST /m03/worn` | Log pieces as worn (today by default); a worn piece is back to available | `item_ids`, `date?`, `outfit_id?`, `posted?`, `source?`, `auto_laundry_after?`, `laundry_categories?` |
| `POST /m03/unworn` | Undo a log | `entry_id` |
| `POST /m03/posted` | Mark a logged look as posted (M2 never re-suggests it) | `entry_id`, `posted` |
| `POST /m03/status` | available / laundry / lent | `item_ids`, `status`, `lent_to?`, `expected_back?`, `note?` |
| `POST /m03/laundry_done` | Laundry (all or `item_ids`) back in the closet | `item_ids?` |
| `POST /m03/states` | Current statuses, `unavailable` list (what M2 excludes), reminders | `item_ids?`, `today?`, `laundry_reminder_days?` |
| `POST /m03/stats` | Per piece: wear_count, last_worn, days_since_worn, wears_30d / 90d, status. Wardrobe summary: utilisation, never worn, forgotten, most worn, repeats | `item_ids?` (the wardrobe), `today?` |
| `POST /m03/history` | Wear log, newest first: `{entry_id, date, item_ids, outfit_key, posted, source}` (`date` + `item_ids` = M2's `wear_log` format) | `since?`, `until?`, `item_id?`, `limit?` |
| `POST /m03/forgotten` | Pieces not worn for N days, most dormant first (never worn first) | `item_ids?`, `days` |
| `POST /m03/recap` | Month: wears, distinct pieces, utilisation, top pieces, first-time pieces, repeated outfits, posted looks | `month?` ("2026-10"), `item_ids?` |
| `GET /m03/demo` | **Lab page** | |

Pass `item_ids` (the user's wardrobe from M1) when you need never-worn pieces: M3 only knows pieces that
were logged or given a status.

```bash
curl -X POST localhost:8000/m03/worn -H "Content-Type: application/json" \
  -d '{"user_id":"u1","payload":{"item_ids":["k_1","k_2","k_3"],"auto_laundry_after":3}}'
```

## Rules (from the BO1 / BO2 prototypes)
* Auto-laundry: after `auto_laundry_after` wears since the last wash, a **top / bottom / dress** goes to the
  laundry (shoes, jackets, accessories never do; pass `laundry_categories` so M3 knows which is which).
* Laundry for `laundry_reminder_days` (3) days → reminder `back_in_closet?`. Lent past `expected_back` →
  `lent_overdue`.
* Logging a piece as worn brings it back to `available` (it obviously is).
* `outfit_key` = sorted item ids: same key = exact same outfit (M2 penalises a repeat within 14 days and never
  re-suggests a posted look).

## Used by M2
M2 (`service._setup`) reads the wear log and `unavailable` from M3 when M3 runs for real: rotation,
forgotten-piece bonus, remix novelty, exact-repeat / posted penalties, laundry & lent exclusion. Demo users
get a synthetic 120-day history imported once (`POST /m03/demo/seed/{user_id}` resets it).

## Storage
SQLAlchemy 2.0 tables `m03_wear_entries`, `m03_wear_items`, `m03_item_status`, created on first use.
* default: SQLite file `backend/modules/m03_wear_log/.data/m03.sqlite` (git-ignored)
* Postgres (docker compose): `M03_DATABASE_URL=postgresql+psycopg2://dressme:change_me@localhost:5432/dressme`
  (`pip install psycopg2-binary`)

## Run it
```bash
cd backend
M02_USE_MOCK=false M03_USE_MOCK=false uvicorn api.main:app --reload
# Windows cmd: set M02_USE_MOCK=false & set M03_USE_MOCK=false & python -m uvicorn api.main:app
# open http://localhost:8000/m03/demo  (and /m02/demo: "Wear it" logs into M3)
pytest -q modules/m03_wear_log
```
`M03_USE_MOCK` overrides the global `USE_MOCKS` for M3 only.
