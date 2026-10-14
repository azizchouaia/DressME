# M4 · Scheduler, notifications + outfit calendar

**Owner:** BO1 / BO2 · **Used by:** BO1 BO2 BO6 BO8

**Includes:** scheduled jobs (05:00 outfit, 07:00 push, 20:00 tomorrow), cache, notifications with actions,
calendar of events / occasions (with Tunisian holidays), event countdown looks, weather tips, laundry
reminders, seasonal refresh trigger, week plan, widget feed.

M4 recommends nothing itself and has no ML model: it decides **when** and **for which day / occasion**, calls
**M2** (outfits) and **M3** (wear log, laundry), caches the results and notifies.

## Jobs (local time of the user, defaults)
| Job | When | What |
|---|---|---|
| `morning` | 05:00 | M2 outfit of the day (occasion from the calendar), cached → the app opens on it in ms. An outfit approved the night before is kept (locked). |
| `notify` | 07:00 | Push "Good morning · Today: … · 14°C, rain" with **Wear** (logs in M3) / **Change** (next option). |
| `evening` | 20:00 | Tomorrow's outfit with tomorrow's forecast + push **Approve** / **Change**; weather tip (rain coming, ±5°C); "Back in your closet?" for pieces 3+ days in the laundry (M3). |
| `events` | 05:00 | Event countdown: 3 looks `remind_days` (5) before, refreshed 2 days before with the forecast, reminder the day before. Festive Tunisian holidays (Aid, Mouled, Women's Day) count as events. |
| `season` | Monday 05:00 | 7-day mean temperature crosses 18°C → "Autumn is back" + 3 looks with forgotten pieces (BO1 seasonal refresh). |

A job is due from its time to 3 hours later and runs **once per user per day** (`m04_job_runs`), so a missed
night is not replayed at 23:00 and a double tick never sends two notifications.

**Occasion of a day:** personal event > festive holiday > other holiday (casual) > weekday default
(Mon–Fri work, Sat–Sun casual, editable).

## Endpoints (prefix `/m04`)
Team envelope `{user_id, payload}` → `{result, mocked}`; payloads are typed in `contract.py`.

| Endpoint | What |
|---|---|
| `POST /m04/schedule` | Preferences (city, timezone, times, weekday occasions, jobs on/off, push token) + next runs. `set` to update. |
| `POST /m04/calendar` | Days with occasion + reason, personal events, Tunisian holidays, seasons, cached outfit. |
| `POST /m04/events/add` · `/events/delete` | Personal events (date, title, occasion, dress code, remind_days). |
| `POST /m04/today` · `/tomorrow` | Cached outfit of the day (computed on demand if missing): outfit, items, weather, occasion reason, option i/n. |
| `POST /m04/approve` · `/change` · `/wear` | Lock / next option (new M2 options after the last) / log in M3. `kind` = `day` or `event:<id>`. |
| `POST /m04/week` | Next 7 days, each its forecast and occasion, no top / bottom / dress twice (BO8 weekly planning). |
| `POST /m04/widget` | Compact today payload + deep link for the home-screen widget (BO2). |
| `POST /m04/notifications` · `/notifications/action` | Outbox (unread count, mark read) · buttons wear / change / approve / back_in_closet / open / dismiss. |
| `POST /m04/run` | Run a job now at an optional simulated time (`job`: morning / notify / evening / events / season / due). |
| `GET /m04/status` · `/m04/demo` | Scheduler status · **lab page** (mobile-friendly). |

## Notifications
Stored in the `m04_notifications` outbox; the app reads it (`/m04/notifications`). Real push needs Firebase:
with an FCM service account, `_push` sends to `prefs.push_token` and sets `delivered = "fcm"` (one function).

## Tunisian calendar (`tunisia.py`, for BO6)
Fixed days (Independence 20/03, Martyrs 09/04, Labour 01/05, Republic 25/07, Women's Day 13/08,
Evacuation 15/10, Revolution 17/12, New Year) + Islamic feasts computed for any year with the arithmetic Hijri
calendar (Ras el Am el Hijri, Mouled, 1st of Ramadan, Aid el Fitr, Aid el Kebir), flagged `approximate`
(±1 day: the official date depends on the moon sighting). Summer wedding season (June–September).

## Scheduler
`scheduler.py`: APScheduler ticks every 5 min (`M04_TICK_MINUTES`) and calls `service.run_due()`. Starts with
the API when M4 is not mocked; `M04_SCHEDULER=off` to disable (e.g. on extra workers, or when Celery beat /
a cron calls `run_due` or `POST /m04/run {"job": "due"}` instead).

## Storage
SQLAlchemy tables `m04_prefs`, `m04_events`, `m04_outfits`, `m04_notifications`, `m04_job_runs`; SQLite file
`modules/m04_scheduler/.data/m04.sqlite` by default, Postgres with
`M04_DATABASE_URL=postgresql+psycopg2://dressme:change_me@localhost:5432/dressme`.

## Run it
```bash
cd backend
pip install -r modules/m04_scheduler/requirements.txt
M02_USE_MOCK=false M03_USE_MOCK=false M04_USE_MOCK=false uvicorn api.main:app
# open http://localhost:8000/m04/demo, use "Simulate the clock" to run 05:00 / 07:00 / 20:00 now
pytest -q modules/m04_scheduler        # M2 mocked: no models needed
```
