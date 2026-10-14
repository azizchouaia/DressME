"""Real implementation of M4 (same signatures as mock.py).

Rule-based orchestration, no model: which day / occasion to plan, calls M2 and M3, caches, notifies.
Jobs are plain functions (run_due / run_job): APScheduler runs them in-process (scheduler.py); a Celery beat
or an external cron can call the same functions, or POST /m04/run.
"""

from __future__ import annotations

import datetime as dt
import time
import uuid
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import delete, select

from . import storage, tunisia
from .contract import (
    OCCASIONS,
    CalendarPayload,
    ChoicePayload,
    DayPayload,
    EventAddPayload,
    EventDeletePayload,
    NotificationActionPayload,
    NotificationsPayload,
    Prefs,
    RunPayload,
    SchedulePayload,
    WeekPayload,
)
from .storage import EventRow, JobRunRow, NotificationRow, OutfitCacheRow, PrefsRow

JOBS = ("morning", "notify", "evening", "events", "season")
WINDOW_H = 3  # a job is due from its time to WINDOW_H hours later (missed runs are not replayed at night)
N_OPTIONS = 3
SEASON_THRESHOLD_C = 18.0  # BO1 seasonal refresh: 7-day mean temperature crossing this value
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _uid(req: dict) -> str:
    return req.get("user_id") or "anonymous"


def _ok(result: dict) -> dict:
    return {"result": result, "mocked": False}


# ---------------- other modules (in-process calls through their public API) ----------------
def _m2():
    from modules.m02_recommendation import router

    return router._impl()


def _m3():
    from modules.m03_wear_log import router

    return router._impl()


def _weather(city: str, day: dt.date) -> dict:
    from modules.m02_recommendation import router

    return router.weather(city, day)["result"]


# ---------------- preferences ----------------
def _prefs_row(s, user: str) -> PrefsRow:
    row = s.get(PrefsRow, user)
    if row is None:
        d = Prefs()
        row = PrefsRow(
            user_id=user,
            city=d.city,
            timezone=d.timezone,
            morning_time=d.morning_time,
            notify_time=d.notify_time,
            evening_time=d.evening_time,
            weekday_occasions=list(d.weekday_occasions),
            jobs=dict(d.jobs),
        )
        s.add(row)
        s.flush()
    return row


def _prefs(row: PrefsRow) -> dict:
    return {
        "city": row.city,
        "timezone": row.timezone,
        "morning_time": row.morning_time,
        "notify_time": row.notify_time,
        "evening_time": row.evening_time,
        "weekday_occasions": row.weekday_occasions,
        "jobs": row.jobs,
        "push_token": row.push_token,
    }


def _tz(row: PrefsRow) -> ZoneInfo:
    try:
        return ZoneInfo(row.timezone)
    except Exception:
        return ZoneInfo("Africa/Tunis")


def _local_now(row: PrefsRow, now: dt.datetime | None = None) -> dt.datetime:
    """Local wall-clock time of the user (naive). A given `now` without tz is taken as local time."""
    if now is None:
        return dt.datetime.now(_tz(row)).replace(tzinfo=None)
    if now.tzinfo is not None:
        return now.astimezone(_tz(row)).replace(tzinfo=None)
    return now


def _at(day: dt.date, hhmm: str) -> dt.datetime:
    h, m = map(int, hhmm.split(":"))
    return dt.datetime.combine(day, dt.time(h, m))


def _job_time(row: PrefsRow, job: str) -> str:
    return {
        "morning": row.morning_time,
        "notify": row.notify_time,
        "evening": row.evening_time,
        "events": row.morning_time,
        "season": row.morning_time,
    }[job]


def next_runs(row: PrefsRow, now: dt.datetime) -> dict[str, str]:
    out = {}
    for job in JOBS:
        if not row.jobs.get(job, True):
            continue
        t = _at(now.date(), _job_time(row, job))
        if job == "season":  # weekly, on Mondays
            t += dt.timedelta(days=(7 - t.weekday()) % 7)
        if t <= now:
            t += dt.timedelta(days=7 if job == "season" else 1)
        out[job] = t.isoformat(timespec="minutes")
    return out


def schedule(req: dict) -> dict:
    p = SchedulePayload.model_validate(req.get("payload") or {})
    user = _uid(req)
    with storage.session() as s, s.begin():
        row = _prefs_row(s, user)
        if p.set:
            merged = Prefs.model_validate({**_prefs(row), **p.set})
            if (
                any(o not in OCCASIONS for o in merged.weekday_occasions)
                or len(merged.weekday_occasions) != 7
            ):
                raise ValueError("weekday_occasions: 7 values among work / casual / event")
            for k, v in merged.model_dump().items():
                setattr(row, k, v)
        return _ok({"prefs": _prefs(row), "next_runs": next_runs(row, _local_now(row, p.now))})


# ---------------- calendar ----------------
def _events(s, user: str, start: dt.date, end: dt.date) -> list[EventRow]:
    q = select(EventRow).where(EventRow.user_id == user, EventRow.date >= start, EventRow.date <= end)
    return list(s.scalars(q.order_by(EventRow.date)))


def _event(e: EventRow) -> dict:
    return {
        "event_id": e.event_id,
        "date": e.date.isoformat(),
        "title": e.title,
        "occasion": e.occasion,
        "dress_code": e.dress_code,
        "notes": e.notes,
        "remind_days": e.remind_days,
        "kind": "personal",
    }


def _holiday(h: dict) -> dict:
    return {**h, "date": h["date"].isoformat(), "event_id": f"h:{h['date'].isoformat()}"}


def occasion_for(row: PrefsRow, day: dt.date, events: list[dict], holidays: list[dict]) -> tuple[str, str]:
    """Occasion of a day and why: a personal event > a festive holiday > the weekday default."""
    if events:
        e = max(events, key=lambda e: ("work", "casual", "event").index(e["occasion"]))
        return e["occasion"], e["title"]
    for h in holidays:
        if h["occasion"] == "event":
            return "event", h["title"]
    if holidays:
        return "casual", holidays[0]["title"]
    occ = row.weekday_occasions[day.weekday()]
    return occ, f"{WEEKDAYS[day.weekday()]} default"


def _day_context(s, row: PrefsRow, day: dt.date) -> dict:
    evs = [_event(e) for e in _events(s, row.user_id, day, day)]
    hols = [_holiday(h) for h in tunisia.holidays(day, day)]
    occ, why = occasion_for(row, day, evs, hols)
    return {
        "occasion": occ,
        "occasion_reason": why,
        "events": evs,
        "holidays": hols,
        "seasons": tunisia.season_of(day),
    }


def calendar(req: dict) -> dict:
    p = CalendarPayload.model_validate(req.get("payload") or {})
    user = _uid(req)
    with storage.session() as s, s.begin():
        row = _prefs_row(s, user)
        start = p.start or _local_now(row).date()
        end = start + dt.timedelta(days=p.days - 1)
        evs = [_event(e) for e in _events(s, user, start, end)]
        hols = [_holiday(h) for h in tunisia.holidays(start, end)] if p.include_holidays else []
        cache = {
            r.date: r
            for r in s.scalars(
                select(OutfitCacheRow).where(
                    OutfitCacheRow.user_id == user,
                    OutfitCacheRow.kind == "day",
                    OutfitCacheRow.date >= start,
                    OutfitCacheRow.date <= end,
                )
            )
        }
        days = []
        for k in range(p.days):
            day = start + dt.timedelta(days=k)
            de = [e for e in evs if e["date"] == day.isoformat()]
            dh = [h for h in hols if h["date"] == day.isoformat()]
            occ, why = occasion_for(row, day, de, dh)
            c = cache.get(day)
            days.append(
                {
                    "date": day.isoformat(),
                    "weekday": WEEKDAYS[day.weekday()],
                    "occasion": occ,
                    "occasion_reason": why,
                    "events": de,
                    "holidays": dh,
                    "seasons": tunisia.season_of(day),
                    "outfit": _summary(c) if c else None,
                    "approved": bool(c and c.approved),
                }
            )
    return _ok({"days": days, "upcoming": [x for x in evs + hols if x["occasion"] == "event"]})


def event_add(req: dict) -> dict:
    p = EventAddPayload.model_validate(req.get("payload") or {})
    if p.occasion not in OCCASIONS:
        raise ValueError("occasion must be work / casual / event")
    with storage.session() as s, s.begin():
        _prefs_row(s, _uid(req))
        e = EventRow(
            event_id=uuid.uuid4().hex[:12],
            user_id=_uid(req),
            date=p.date,
            title=p.title,
            occasion=p.occasion,
            dress_code=p.dress_code,
            notes=p.notes,
            remind_days=p.remind_days,
        )
        s.add(e)
        # the day's cached outfit was planned for another occasion
        s.execute(
            delete(OutfitCacheRow).where(
                OutfitCacheRow.user_id == e.user_id,
                OutfitCacheRow.date == p.date,
                OutfitCacheRow.kind == "day",
                OutfitCacheRow.approved.is_(False),
            )
        )
        return _ok({"event": _event(e)})


def event_delete(req: dict) -> dict:
    p = EventDeletePayload.model_validate(req.get("payload") or {})
    with storage.session() as s, s.begin():
        e = s.get(EventRow, p.event_id)
        if e is None or e.user_id != _uid(req):
            return _ok({"deleted": False})
        s.execute(
            delete(OutfitCacheRow).where(
                OutfitCacheRow.user_id == e.user_id, OutfitCacheRow.kind == f"event:{e.event_id}"
            )
        )
        s.delete(e)
    return _ok({"deleted": True})


# ---------------- outfits (cache) ----------------
def _names(result: dict, outfit: dict) -> str:
    items = result.get("items", {})
    order = ["outerwear", "top", "dress", "bottom", "shoes", "accessory"]
    ids = sorted(
        outfit["items"],
        key=lambda i: (
            order.index(items.get(i, {}).get("category", "accessory"))
            if items.get(i, {}).get("category") in order
            else 9
        ),
    )
    return " + ".join(items.get(i, {}).get("name", i) for i in ids)


def _current(r: OutfitCacheRow) -> dict | None:
    outs = r.result.get("outfits") or []
    return outs[r.choice % len(outs)] if outs else None


def _summary(r: OutfitCacheRow) -> dict | None:
    o = _current(r)
    if o is None:
        return None
    w = (r.result.get("context") or {}).get("weather") or {}
    return {
        "items": o["items"],
        "text": _names(r.result, o),
        "temp_c": w.get("temp_c"),
        "condition": w.get("condition"),
    }


def _view(r: OutfitCacheRow, ctx: dict | None = None) -> dict:
    o = _current(r)
    items = r.result.get("items", {})
    return {
        "date": r.date.isoformat(),
        "kind": r.kind,
        "occasion": r.occasion,
        "approved": r.approved,
        "choice": r.choice,
        "options": len(r.result.get("outfits") or []),
        "source": r.source,
        "computed_at": r.computed_at.isoformat(timespec="seconds") + "Z",  # UTC
        "weather": (r.result.get("context") or {}).get("weather"),
        "weather_source": r.result.get("weather_source"),
        "outfit": o,
        "summary": _names(r.result, o) if o else None,
        "items": {i: items[i] for i in (o["items"] if o else []) if i in items},
        "context": ctx,
    }


def _compute(
    s,
    row: PrefsRow,
    day: dt.date,
    kind: str,
    occasion: str,
    source: str,
    exclude: list[str] | None = None,
    options: dict | None = None,
) -> OutfitCacheRow:
    req = {
        "user_id": row.user_id,
        "payload": {
            "context": {"occasion": occasion, "city": row.city, "date": day.isoformat()},
            "options": {"n": N_OPTIONS, "exclude_item_ids": exclude or [], **(options or {})},
        },
    }
    result = _m2().recommend(req)["result"]
    cached = s.get(OutfitCacheRow, (row.user_id, day, kind))
    if cached is None:
        cached = OutfitCacheRow(user_id=row.user_id, date=day, kind=kind)
        s.add(cached)
    cached.result, cached.choice, cached.approved = result, 0, False
    cached.occasion, cached.source, cached.computed_at = occasion, source, storage._now()
    s.flush()
    return cached


def _get_day(s, row: PrefsRow, day: dt.date, source: str, refresh: bool = False) -> OutfitCacheRow:
    cached = s.get(OutfitCacheRow, (row.user_id, day, "day"))
    if cached is not None and not refresh:
        return cached
    ctx = _day_context(s, row, day)
    return _compute(s, row, day, "day", ctx["occasion"], source)


def day(req: dict) -> dict:
    """Outfit of a day (today by default): from the cache in < 1 s, computed on demand if missing."""
    p = DayPayload.model_validate(req.get("payload") or {})
    with storage.session() as s, s.begin():
        row = _prefs_row(s, _uid(req))
        d = p.date or _local_now(row).date()
        r = _get_day(s, row, d, "on_demand", p.refresh)
        return _ok(_view(r, _day_context(s, row, d)))


def tomorrow(req: dict) -> dict:
    with storage.session() as s, s.begin():
        row = _prefs_row(s, _uid(req))
        d = _local_now(row).date() + dt.timedelta(days=1)
    payload = {**(req.get("payload") or {}), "date": d.isoformat()}
    return day({"user_id": req.get("user_id"), "payload": payload})


def _cached(s, row: PrefsRow, p: ChoicePayload) -> OutfitCacheRow:
    d = p.date or _local_now(row).date()
    if p.kind == "day":
        return _get_day(s, row, d, "on_demand")
    r = s.get(OutfitCacheRow, (row.user_id, d, p.kind))
    if r is None:
        raise ValueError(f"nothing cached for {p.kind} on {d}")
    return r


def approve(req: dict) -> dict:
    p = ChoicePayload.model_validate(req.get("payload") or {})
    with storage.session() as s, s.begin():
        row = _prefs_row(s, _uid(req))
        r = _cached(s, row, p)
        r.approved = True
        return _ok(_view(r))


def change(req: dict) -> dict:
    """Next option; after the last one, M2 computes new options without the pieces already shown."""
    p = ChoicePayload.model_validate(req.get("payload") or {})
    with storage.session() as s, s.begin():
        row = _prefs_row(s, _uid(req))
        r = _cached(s, row, p)
        outs = r.result.get("outfits") or []
        if r.choice + 1 < len(outs):
            r.choice += 1
            r.approved = False
        else:
            items = r.result.get("items", {})
            shown = [
                i
                for o in outs
                for i in o["items"]
                if items.get(i, {}).get("category") in ("top", "dress", "bottom")
            ]
            r = _compute(s, row, r.date, r.kind, r.occasion, "change", exclude=shown)
        return _ok(_view(r))


def wear(req: dict) -> dict:
    """Log the current option as worn in M3 (auto-laundry after 3 wears) and lock it."""
    p = ChoicePayload.model_validate(req.get("payload") or {})
    with storage.session() as s, s.begin():
        row = _prefs_row(s, _uid(req))
        r = _cached(s, row, p)
        o = _current(r)
        r.approved = True
        view = _view(r)
    items = view["items"]
    logged = _m3().worn(
        {
            "user_id": row.user_id,
            "payload": {
                "item_ids": o["items"],
                "date": r.date.isoformat(),
                "outfit_id": o.get("outfit_id"),
                "source": "scheduled",
                "auto_laundry_after": 3,
                "laundry_categories": {i: v.get("category") for i, v in items.items()},
            },
        }
    )
    return _ok({**view, "logged": logged["result"]})


# ---------------- week plan ----------------
def week(req: dict) -> dict:
    """Outfits for the next days (BO8 weekly planning): each day its forecast and occasion, no top / bottom /
    dress worn twice in the plan."""
    p = WeekPayload.model_validate(req.get("payload") or {})
    out = []
    with storage.session() as s, s.begin():
        row = _prefs_row(s, _uid(req))
        start = p.start or _local_now(row).date()
        used: list[str] = []
        for k in range(p.days):
            d = start + dt.timedelta(days=k)
            r = s.get(OutfitCacheRow, (row.user_id, d, "day"))
            if r is None or (p.refresh and not r.approved):
                ctx = _day_context(s, row, d)
                r = _compute(s, row, d, "day", ctx["occasion"], "week", exclude=used)
            o = _current(r)
            items = r.result.get("items", {})
            used += [
                i
                for i in (o["items"] if o else [])
                if items.get(i, {}).get("category") in ("top", "dress", "bottom")
            ]
            out.append(_view(r, _day_context(s, row, d)))
    return _ok({"days": out})


# ---------------- widget ----------------
def widget(req: dict) -> dict:
    """Compact "today" payload for the home-screen widget (BO2)."""
    v = day({"user_id": req.get("user_id"), "payload": {}})["result"]
    w = v["weather"] or {}
    return _ok(
        {
            "date": v["date"],
            "temp_c": w.get("temp_c"),
            "condition": w.get("condition"),
            "occasion": v["occasion"],
            "summary": v["summary"],
            "approved": v["approved"],
            "items": [
                {"item_id": i, "name": x.get("name"), "image": x.get("image"), "category": x.get("category")}
                for i, x in v["items"].items()
            ],
            "deep_link": f"dressme://today?date={v['date']}",
        }
    )


# ---------------- notifications ----------------
def _push(s, row: PrefsRow, kind: str, title: str, body: str, data: dict, actions: list[str]) -> dict:
    n = NotificationRow(
        notif_id=_time_id(),
        user_id=row.user_id,
        kind=kind,
        title=title,
        body=body,
        data=data,
        actions=actions,
        status="unread",
        delivered="outbox",
    )
    s.add(n)
    s.flush()
    # Delivery: the app reads the outbox (POST /m04/notifications). With Firebase credentials, a sender would
    # post to FCM here using row.push_token and set n.delivered = "fcm".
    return _notif(n)


_last_id = 0


def _time_id() -> str:
    """Time-ordered id (hex nanoseconds, strictly increasing in this process) + random suffix."""
    global _last_id
    _last_id = max(_last_id + 1, time.time_ns())
    return f"{_last_id:016x}{uuid.uuid4().hex[:6]}"


def _notif(n: NotificationRow) -> dict:
    return {
        "notif_id": n.notif_id,
        "kind": n.kind,
        "title": n.title,
        "body": n.body,
        "data": n.data,
        "actions": n.actions,
        "status": n.status,
        "action_taken": n.action_taken,
        "delivered": n.delivered,
        "created_at": n.created_at.isoformat(timespec="seconds") + "Z",  # UTC
    }


def notifications(req: dict) -> dict:
    p = NotificationsPayload.model_validate(req.get("payload") or {})
    with storage.session() as s, s.begin():
        user = _uid(req)
        if p.mark_read:
            for n in s.scalars(select(NotificationRow).where(NotificationRow.notif_id.in_(p.mark_read))):
                if n.user_id == user and n.status == "unread":
                    n.status = "read"
        q = select(NotificationRow).where(NotificationRow.user_id == user)
        if p.status:
            q = q.where(NotificationRow.status == p.status)
        rows = list(
            s.scalars(
                q.order_by(NotificationRow.created_at.desc(), NotificationRow.notif_id.desc()).limit(p.limit)
            )
        )
        unread = len(
            list(
                s.scalars(
                    select(NotificationRow.notif_id).where(
                        NotificationRow.user_id == user, NotificationRow.status == "unread"
                    )
                )
            )
        )
        return _ok({"notifications": [_notif(n) for n in rows], "unread": unread})


def notification_action(req: dict) -> dict:
    """The buttons of a notification: wear / change / approve / back_in_closet / open / dismiss."""
    p = NotificationActionPayload.model_validate(req.get("payload") or {})
    user = _uid(req)
    with storage.session() as s, s.begin():
        n = s.get(NotificationRow, p.notif_id)
        if n is None or n.user_id != user:
            raise ValueError("unknown notification")
        data = dict(n.data)
        n.status, n.action_taken = ("acted" if p.action not in ("open", "dismiss") else "read"), p.action
    choice = {"user_id": user, "payload": {"date": data.get("date"), "kind": data.get("kind", "day")}}
    if p.action == "wear":
        return wear(choice)
    if p.action == "change":
        return change(choice)
    if p.action == "approve":
        return approve(choice)
    if p.action == "back_in_closet":
        return _ok(
            _m3().laundry_done({"user_id": user, "payload": {"item_ids": data.get("item_ids")}})["result"]
        )
    return _ok({"notif_id": p.notif_id, "status": "read"})


# ---------------- jobs ----------------
def _ran(s, user: str, key: str) -> bool:
    return s.get(JobRunRow, (user, key)) is not None


def _mark(s, user: str, key: str, summary: str) -> None:
    r = s.get(JobRunRow, (user, key))
    if r is None:
        s.add(JobRunRow(user_id=user, run_key=key, summary=summary[:250]))
    else:
        r.ran_at, r.summary = storage._now(), summary[:250]


def _weather_line(r: OutfitCacheRow) -> str:
    w = (r.result.get("context") or {}).get("weather") or {}
    return f"{w.get('temp_c', '?'):.0f}°C, {w.get('condition', '')}" if w.get("temp_c") is not None else ""


def _job_morning(s, row: PrefsRow, now: dt.datetime) -> dict:
    today = now.date()
    r = s.get(OutfitCacheRow, (row.user_id, today, "day"))
    if r is not None and r.approved:
        return {
            "today": today.isoformat(),
            "kept": "approved the night before",
            "summary": _names(r.result, _current(r)),
        }
    r = _get_day(s, row, today, "morning", refresh=True)
    return {"today": today.isoformat(), "computed": True, "summary": _names(r.result, _current(r))}


def _job_notify(s, row: PrefsRow, now: dt.datetime) -> dict:
    today = now.date()
    r = _get_day(s, row, today, "on_demand")
    ctx = _day_context(s, row, today)
    o = _current(r)
    items = r.result.get("items", {})
    n = _push(
        s,
        row,
        "daily",
        f"Good morning · {ctx['occasion_reason']}",
        f"Today: {_names(r.result, o)} · {_weather_line(r)}",
        {
            "date": today.isoformat(),
            "kind": "day",
            "outfit_id": o.get("outfit_id"),
            "images": [items.get(i, {}).get("image") for i in o["items"]],
        },
        ["wear", "change"],
    )
    return {"notification": n}


def _job_evening(s, row: PrefsRow, now: dt.datetime) -> dict:
    today, tom = now.date(), now.date() + dt.timedelta(days=1)
    out: dict = {"tomorrow": tom.isoformat()}
    r = s.get(OutfitCacheRow, (row.user_id, tom, "day"))
    if r is None or not r.approved:
        r = _get_day(s, row, tom, "evening", refresh=True)
    ctx = _day_context(s, row, tom)
    o = _current(r)
    items = r.result.get("items", {})
    out["notification"] = _push(
        s,
        row,
        "tomorrow",
        f"Tomorrow · {WEEKDAYS[tom.weekday()]} · {ctx['occasion_reason']}",
        f"{_weather_line(r)} · {_names(r.result, o)}",
        {
            "date": tom.isoformat(),
            "kind": "day",
            "outfit_id": o.get("outfit_id"),
            "images": [items.get(i, {}).get("image") for i in o["items"]],
        },
        ["approve", "change"],
    )
    if row.jobs.get("weather_tips", True):
        tip = _weather_tip(row, today, tom)
        if tip:
            out["weather_tip"] = _push(
                s, row, "weather_tip", tip[0], tip[1], {"date": tom.isoformat()}, ["open"]
            )
    if row.jobs.get("laundry", True):
        st = _m3().states({"user_id": row.user_id, "payload": {"today": today.isoformat()}})["result"]
        waiting = [x["item_id"] for x in st.get("reminders", []) if x["reminder"] == "back_in_closet?"]
        if waiting:
            out["laundry"] = _push(
                s,
                row,
                "laundry",
                "Back in your closet?",
                f"{len(waiting)} piece(s) have been in the laundry for a few days.",
                {"item_ids": waiting},
                ["back_in_closet", "dismiss"],
            )
    return out


def _weather_tip(row: PrefsRow, today: dt.date, tom: dt.date) -> tuple[str, str] | None:
    """BO8 proactive tip: rain coming, or a big temperature change between today and tomorrow."""
    a, b = _weather(row.city, today), _weather(row.city, tom)
    if b.get("source") == "fallback":
        return None
    rainy = b["condition"] in ("drizzle", "rain", "storm", "snow")
    if rainy and a["condition"] not in ("drizzle", "rain", "storm", "snow"):
        return (
            "Rain tomorrow",
            f"{b['condition'].capitalize()} expected in {row.city}: a jacket and closed shoes.",
        )
    if b["temp_c"] <= a["temp_c"] - 5:
        return "Colder tomorrow", f"{b['temp_c']:.0f}°C tomorrow vs {a['temp_c']:.0f}°C today: add a layer."
    if b["temp_c"] >= a["temp_c"] + 5:
        return "Warmer tomorrow", f"{b['temp_c']:.0f}°C tomorrow vs {a['temp_c']:.0f}°C today: go lighter."
    return None


def _job_events(s, row: PrefsRow, now: dt.datetime) -> dict:
    """Event countdown (BO2 P12): 3 looks X days before, refresh 2 days before, reminder the day before.
    Festive Tunisian holidays (Aid, Mouled...) count as events."""
    today = now.date()
    horizon = today + dt.timedelta(days=30)
    targets = [_event(e) for e in _events(s, row.user_id, today + dt.timedelta(days=1), horizon)]
    targets += [
        {**_holiday(h), "remind_days": 5}
        for h in tunisia.holidays(today + dt.timedelta(days=1), horizon)
        if h["occasion"] == "event" and not h["title"].endswith("(day 2)")
    ]
    done = []
    for e in targets:
        d = dt.date.fromisoformat(e["date"])
        left = (d - today).days
        if left > e["remind_days"]:
            continue
        kind = f"event:{e['event_id']}"
        cached = s.get(OutfitCacheRow, (row.user_id, d, kind))
        if cached is None:
            r = _compute(s, row, d, kind, e["occasion"], "event")
            n = _push(
                s,
                row,
                "event_shortlist",
                f"{e['title']} in {left} day(s)",
                f"{len(r.result.get('outfits') or [])} looks ready: {_names(r.result, _current(r))}…",
                {"date": e["date"], "kind": kind, "event": e},
                ["open"],
            )
            done.append({"event": e["title"], "step": "shortlist", "notification": n})
        elif left <= 2 and not _ran(s, row.user_id, f"event-refresh:{e['event_id']}") and not cached.approved:
            _compute(s, row, d, kind, e["occasion"], "event_refresh")
            _mark(s, row.user_id, f"event-refresh:{e['event_id']}", "refreshed with the forecast")
            done.append({"event": e["title"], "step": "refreshed with the forecast"})
        if left == 1 and not _ran(s, row.user_id, f"event-remind:{e['event_id']}"):
            r = s.get(OutfitCacheRow, (row.user_id, d, kind))
            n = _push(
                s,
                row,
                "event_reminder",
                f"Tomorrow: {e['title']}",
                f"Your look: {_names(r.result, _current(r))} · {_weather_line(r)}",
                {"date": e["date"], "kind": kind, "event": e},
                ["approve", "change"],
            )
            _mark(s, row.user_id, f"event-remind:{e['event_id']}", "reminder sent")
            done.append({"event": e["title"], "step": "reminder", "notification": n})
    return {"events": done}


def _temperature_trend(city: str) -> tuple[float, float] | None:
    """Mean daily temperature of the last 7 days and of the next 7 days (Open-Meteo)."""
    try:
        with httpx.Client(timeout=5) as c:
            geo = c.get(
                "https://geocoding-api.open-meteo.com/v1/search", params={"name": city, "count": 1}
            ).json()
            g = geo["results"][0]
            d = c.get(
                "https://api.open-meteo.com/v1/forecast",
                params={
                    "latitude": g["latitude"],
                    "longitude": g["longitude"],
                    "daily": "temperature_2m_mean",
                    "past_days": 7,
                    "forecast_days": 7,
                    "timezone": "auto",
                },
            ).json()["daily"]["temperature_2m_mean"]
        return sum(d[:7]) / 7, sum(d[7:]) / len(d[7:])
    except Exception:
        return None


def _job_season(s, row: PrefsRow, now: dt.datetime) -> dict:
    """BO1 seasonal refresh: the 7-day mean temperature crosses 18°C -> resurface last season's pieces."""
    trend = _temperature_trend(row.city)
    if trend is None:
        return {"season": "weather unavailable"}
    past, nxt = trend
    if past >= SEASON_THRESHOLD_C > nxt:
        title, body, kind = (
            "Autumn is back",
            "Your jackets and long sleeves return: 3 looks around them.",
            "autumn",
        )
    elif past < SEASON_THRESHOLD_C <= nxt:
        title, body, kind = "Summer is coming", "Light pieces are back: 3 looks around them.", "summer"
    else:
        return {"season": "no change", "past_7d": round(past, 1), "next_7d": round(nxt, 1)}
    occ = row.weekday_occasions[now.weekday()]
    r = _compute(s, row, now.date(), f"season:{kind}", occ, "season", options={"forgotten_after_days": 45})
    n = _push(
        s, row, "season", title, body, {"date": now.date().isoformat(), "kind": f"season:{kind}"}, ["open"]
    )
    return {
        "season": kind,
        "past_7d": round(past, 1),
        "next_7d": round(nxt, 1),
        "notification": n,
        "summary": _names(r.result, _current(r)),
    }


_JOBS = {
    "morning": _job_morning,
    "notify": _job_notify,
    "evening": _job_evening,
    "events": _job_events,
    "season": _job_season,
}


def _run_key(job: str, now: dt.datetime) -> str:
    if job == "season":
        y, w, _ = now.isocalendar()
        return f"season:{y}-W{w:02d}"
    return f"{job}:{now.date().isoformat()}"


def _due(row: PrefsRow, job: str, now: dt.datetime) -> bool:
    if not row.jobs.get(job, True):
        return False
    if job == "season" and now.weekday() != 0:
        return False
    t = _at(now.date(), _job_time(row, job))
    return t <= now < t + dt.timedelta(hours=WINDOW_H)


def run_due(
    now_utc: dt.datetime | None = None, user_id: str | None = None, local_now: dt.datetime | None = None
) -> list[dict]:
    """Run every job that is due for every scheduled user (called every few minutes by the scheduler)."""
    with storage.session() as s:
        users = [user_id] if user_id else list(s.scalars(select(PrefsRow.user_id)))
    runs = []
    for user in users:
        with storage.session() as s, s.begin():
            row = _prefs_row(s, user)
            now = local_now or _local_now(row, now_utc)
            for job in JOBS:
                key = _run_key(job, now)
                if _due(row, job, now) and not _ran(s, user, key):
                    try:
                        res = _JOBS[job](s, row, now)
                        _mark(s, user, key, str(res)[:250])
                        runs.append(
                            {
                                "user_id": user,
                                "job": job,
                                "at": now.isoformat(timespec="minutes"),
                                "result": res,
                            }
                        )
                    except Exception as e:  # one failing user / job never blocks the others
                        runs.append({"user_id": user, "job": job, "error": repr(e)})
    return runs


def run(req: dict) -> dict:
    """Run a job now for this user (demo / tests / external cron). job="due" runs whatever is due at `now`."""
    p = RunPayload.model_validate(req.get("payload") or {})
    user = _uid(req)
    if p.job in (None, "due"):
        with storage.session() as s, s.begin():
            row = _prefs_row(s, user)
            now = _local_now(row, p.now)
        return _ok({"runs": run_due(user_id=user, local_now=now)})
    if p.job not in _JOBS:
        raise ValueError(f"job must be one of {', '.join(JOBS)} or due")
    with storage.session() as s, s.begin():
        row = _prefs_row(s, user)
        now = _local_now(row, p.now)
        res = _JOBS[p.job](s, row, now)
        _mark(s, user, _run_key(p.job, now), str(res)[:250])
    return _ok(
        {"runs": [{"user_id": user, "job": p.job, "at": now.isoformat(timespec="minutes"), "result": res}]}
    )


def reset(user_id: str) -> None:
    with storage.session() as s, s.begin():
        for t in (EventRow, OutfitCacheRow, NotificationRow, JobRunRow, PrefsRow):
            s.execute(delete(t).where(t.user_id == user_id))
