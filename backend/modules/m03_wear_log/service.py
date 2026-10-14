"""Real implementation of M3 (same signatures as mock.py). Rule-based, no model: a log and statistics."""

from __future__ import annotations

import datetime as dt
import uuid
from collections import Counter

from sqlalchemy import delete, select

from . import storage
from .contract import (
    ForgottenPayload,
    HistoryPayload,
    ItemStatus,
    LaundryDonePayload,
    PostedPayload,
    QueryPayload,
    RecapPayload,
    StatsPayload,
    StatusPayload,
    UnwornPayload,
    WornPayload,
)
from .storage import ItemStatusRow, WearEntryRow, WearItemRow

LAUNDRY_CATEGORIES = {"top", "bottom", "dress"}  # auto-laundry applies to clothes, not shoes / jackets


def _uid(req: dict) -> str:
    return req.get("user_id") or "anonymous"


def outfit_key(item_ids: list[str]) -> str:
    return "+".join(sorted(set(item_ids)))


def _ok(result: dict) -> dict:
    return {"result": result, "mocked": False}


def _entry(e: WearEntryRow) -> dict:
    return {
        "entry_id": e.entry_id,
        "date": e.date.isoformat(),
        "item_ids": e.outfit_key.split("+"),
        "outfit_key": e.outfit_key,
        "outfit_id": e.outfit_id,
        "posted": e.posted,
        "source": e.source,
    }


def _state(row: ItemStatusRow | None, item_id: str, today: dt.date, reminder_days: int = 3) -> dict:
    if row is None:
        return {
            "item_id": item_id,
            "status": "available",
            "status_since": None,
            "lent_to": None,
            "expected_back": None,
            "note": None,
            "wears_since_wash": 0,
            "reminder": None,
        }
    reminder = None
    if row.status == "laundry" and row.since and (today - row.since).days >= reminder_days:
        reminder = "back_in_closet?"
    if row.status == "lent" and row.expected_back and today > row.expected_back:
        reminder = "lent_overdue"
    return {
        "item_id": item_id,
        "status": row.status,
        "status_since": row.since and row.since.isoformat(),
        "lent_to": row.lent_to,
        "expected_back": row.expected_back and row.expected_back.isoformat(),
        "note": row.note,
        "wears_since_wash": row.wears_since_wash,
        "reminder": reminder,
    }


def _status_rows(s, user: str) -> dict[str, ItemStatusRow]:
    return {r.item_id: r for r in s.scalars(select(ItemStatusRow).where(ItemStatusRow.user_id == user))}


def _entries(s, user: str) -> list[WearEntryRow]:
    q = (
        select(WearEntryRow)
        .where(WearEntryRow.user_id == user)
        .order_by(WearEntryRow.date.desc(), WearEntryRow.created_at.desc())
    )
    return list(s.scalars(q))


# ---------------- writes ----------------
def worn(req: dict) -> dict:
    p = WornPayload.model_validate(req.get("payload") or {})
    user, day = _uid(req), p.date or dt.date.today()
    ids = sorted(set(p.item_ids))
    if not ids:
        return _ok({"entry": None, "moved_to_laundry": []})
    moved = []
    with storage.session() as s, s.begin():
        e = WearEntryRow(
            entry_id=uuid.uuid4().hex,
            user_id=user,
            date=day,
            outfit_key=outfit_key(ids),
            outfit_id=p.outfit_id,
            posted=p.posted,
            source=p.source,
        )
        s.add(e)
        rows = _status_rows(s, user)
        for i in ids:
            s.add(WearItemRow(entry_id=e.entry_id, item_id=i, user_id=user, date=day))
            row = rows.get(i)
            if row is None:
                row = ItemStatusRow(user_id=user, item_id=i, status="available", wears_since_wash=0)
                s.add(row)
            if row.status != "available":  # wearing it means it is back (from the laundry, or returned)
                row.status, row.since, row.lent_to, row.expected_back = "available", day, None, None
            row.wears_since_wash = (row.wears_since_wash or 0) + 1
            cat = p.laundry_categories.get(i)
            if (
                p.auto_laundry_after
                and row.wears_since_wash >= p.auto_laundry_after
                and (cat is None or cat in LAUNDRY_CATEGORIES)
            ):
                row.status, row.since, row.wears_since_wash = "laundry", day, 0
                moved.append(i)
            row.updated_at = dt.datetime.utcnow()
        entry = _entry(e)
    return _ok({"entry": entry, "moved_to_laundry": moved})


def unworn(req: dict) -> dict:
    p = UnwornPayload.model_validate(req.get("payload") or {})
    user = _uid(req)
    with storage.session() as s, s.begin():
        e = s.get(WearEntryRow, p.entry_id)
        if e is None or e.user_id != user:
            return _ok({"removed": False})
        rows = _status_rows(s, user)
        for i in e.outfit_key.split("+"):
            r = rows.get(i)
            if r is not None and r.wears_since_wash:
                r.wears_since_wash -= 1
        s.execute(delete(WearItemRow).where(WearItemRow.entry_id == e.entry_id))
        s.delete(e)
    return _ok({"removed": True, "entry_id": p.entry_id})


def posted(req: dict) -> dict:
    p = PostedPayload.model_validate(req.get("payload") or {})
    with storage.session() as s, s.begin():
        e = s.get(WearEntryRow, p.entry_id)
        if e is None or e.user_id != _uid(req):
            return _ok({"entry": None})
        e.posted = p.posted
        return _ok({"entry": _entry(e)})


def status(req: dict) -> dict:
    p = StatusPayload.model_validate(req.get("payload") or {})
    user, today = _uid(req), dt.date.today()
    out = []
    with storage.session() as s, s.begin():
        rows = _status_rows(s, user)
        for i in sorted(set(p.item_ids)):
            row = rows.get(i) or ItemStatusRow(user_id=user, item_id=i, wears_since_wash=0)
            s.add(row)
            row.status, row.since, row.note = p.status.value, today, p.note
            row.lent_to = p.lent_to if p.status == ItemStatus.lent else None
            row.expected_back = p.expected_back if p.status == ItemStatus.lent else None
            if p.status == ItemStatus.laundry:
                row.wears_since_wash = 0
            row.updated_at = dt.datetime.utcnow()
            out.append(_state(row, i, today))
    return _ok({"items": out})


def laundry_done(req: dict) -> dict:
    p = LaundryDonePayload.model_validate(req.get("payload") or {})
    user, today = _uid(req), dt.date.today()
    back = []
    with storage.session() as s, s.begin():
        for row in _status_rows(s, user).values():
            if row.status == "laundry" and (p.item_ids is None or row.item_id in p.item_ids):
                row.status, row.since, row.wears_since_wash = "available", today, 0
                back.append(row.item_id)
    return _ok({"back_in_closet": sorted(back)})


# ---------------- reads ----------------
def states(req: dict) -> dict:
    """Status of every piece (or of item_ids), with reminders; `unavailable` is what M2 must exclude."""
    p = QueryPayload.model_validate(req.get("payload") or {})
    user, today = _uid(req), p.today or dt.date.today()
    with storage.session() as s:
        rows = _status_rows(s, user)
    ids = p.item_ids if p.item_ids is not None else sorted(rows)
    items = [_state(rows.get(i), i, today, p.laundry_reminder_days) for i in ids]
    return _ok(
        {
            "items": items,
            "unavailable": [x["item_id"] for x in items if x["status"] != "available"],
            "reminders": [x for x in items if x["reminder"]],
        }
    )


def _per_item(entries: list[WearEntryRow], today: dt.date) -> dict[str, dict]:
    per: dict[str, dict] = {}
    for e in entries:
        if e.date > today:
            continue
        for i in e.outfit_key.split("+"):
            d = per.setdefault(
                i, {"wear_count": 0, "last_worn": None, "first_worn": None, "wears_30d": 0, "wears_90d": 0}
            )
            d["wear_count"] += 1
            d["last_worn"] = max(d["last_worn"] or e.date, e.date)
            d["first_worn"] = min(d["first_worn"] or e.date, e.date)
            age = (today - e.date).days
            d["wears_30d"] += age < 30
            d["wears_90d"] += age < 90
    return per


def stats(req: dict) -> dict:
    p = StatsPayload.model_validate(req.get("payload") or {})
    user, today = _uid(req), p.today or dt.date.today()
    with storage.session() as s:
        entries = _entries(s, user)
        rows = _status_rows(s, user)
    per = _per_item(entries, today)
    ids = list(dict.fromkeys((p.item_ids or []) + sorted(per) + sorted(rows)))
    items = []
    for i in ids:
        d = per.get(
            i, {"wear_count": 0, "last_worn": None, "first_worn": None, "wears_30d": 0, "wears_90d": 0}
        )
        st = _state(rows.get(i), i, today, p.laundry_reminder_days)
        items.append(
            {
                **st,
                **d,
                "last_worn": d["last_worn"] and d["last_worn"].isoformat(),
                "first_worn": d["first_worn"] and d["first_worn"].isoformat(),
                "days_since_worn": (today - d["last_worn"]).days if d["last_worn"] else None,
            }
        )
    recent = [e for e in entries if 0 <= (today - e.date).days < 30]
    worn_30 = {i for e in recent for i in e.outfit_key.split("+")}
    repeats = sum(n - 1 for n in Counter(e.outfit_key for e in recent).values() if n > 1)
    wardrobe = p.item_ids if p.item_ids is not None else ids
    summary = {
        "pieces": len(wardrobe),
        "worn_30d": len(worn_30 & set(wardrobe)),
        "utilisation_30d": round(len(worn_30 & set(wardrobe)) / max(1, len(wardrobe)), 3),
        "never_worn": [i for i in wardrobe if i not in per],
        "forgotten_60d": [
            x["item_id"]
            for x in items
            if x["item_id"] in set(wardrobe) and (x["days_since_worn"] is None or x["days_since_worn"] >= 60)
        ],
        "most_worn": [
            x["item_id"] for x in sorted(items, key=lambda x: -x["wear_count"])[:5] if x["wear_count"]
        ],
        "in_laundry": [x["item_id"] for x in items if x["status"] == "laundry"],
        "lent": [x["item_id"] for x in items if x["status"] == "lent"],
        "outfits_logged": len(entries),
        "repeated_outfits_30d": repeats,
    }
    return _ok({"items": items, "summary": summary, "today": today.isoformat()})


def history(req: dict) -> dict:
    """Wear log, newest first. `entries[*]` has {date, item_ids}: the `wear_log` format M2 takes."""
    p = HistoryPayload.model_validate(req.get("payload") or {})
    user = _uid(req)
    with storage.session() as s:
        q = select(WearEntryRow).where(WearEntryRow.user_id == user)
        if p.since:
            q = q.where(WearEntryRow.date >= p.since)
        if p.until:
            q = q.where(WearEntryRow.date <= p.until)
        if p.item_id:
            q = q.where(
                WearEntryRow.entry_id.in_(
                    select(WearItemRow.entry_id).where(
                        WearItemRow.user_id == user, WearItemRow.item_id == p.item_id
                    )
                )
            )
        rows = list(
            s.scalars(q.order_by(WearEntryRow.date.desc(), WearEntryRow.created_at.desc()).limit(p.limit))
        )
    return _ok({"entries": [_entry(e) for e in rows]})


def forgotten(req: dict) -> dict:
    """Pieces not worn for `days` days, most dormant first (never worn first of all)."""
    p = ForgottenPayload.model_validate(req.get("payload") or {})
    res = stats({"user_id": req.get("user_id"), "payload": p.model_dump()})["result"]
    wardrobe = set(p.item_ids) if p.item_ids is not None else None
    out = [
        x
        for x in res["items"]
        if (wardrobe is None or x["item_id"] in wardrobe)
        and (x["days_since_worn"] is None or x["days_since_worn"] >= p.days)
    ]
    out.sort(key=lambda x: -(x["days_since_worn"] if x["days_since_worn"] is not None else 10**6))
    return _ok(
        {
            "items": [
                {
                    "item_id": x["item_id"],
                    "days_since_worn": x["days_since_worn"],
                    "wear_count": x["wear_count"],
                    "last_worn": x["last_worn"],
                    "status": x["status"],
                }
                for x in out
            ],
            "days": p.days,
        }
    )


def recap(req: dict) -> dict:
    """Monthly recap (BO7 recap card, BO4 insights)."""
    p = RecapPayload.model_validate(req.get("payload") or {})
    today = dt.date.today()
    y, m = map(int, (p.month or today.strftime("%Y-%m")).split("-"))
    start = dt.date(y, m, 1)
    end = dt.date(y + (m == 12), m % 12 + 1, 1)
    with storage.session() as s:
        entries = _entries(s, _uid(req))
    month = [e for e in entries if start <= e.date < end]
    before = {i for e in entries if e.date < start for i in e.outfit_key.split("+")}
    wears = Counter(i for e in month for i in e.outfit_key.split("+"))
    outfits = Counter(e.outfit_key for e in month)
    distinct = len(wears)
    return _ok(
        {
            "month": f"{y:04d}-{m:02d}",
            "days_logged": len({e.date for e in month}),
            "wears": sum(wears.values()),
            "distinct_pieces": distinct,
            "utilisation": round(distinct / len(p.item_ids), 3) if p.item_ids else None,
            "top_pieces": [{"item_id": i, "wears": n} for i, n in wears.most_common(5)],
            "first_time_worn": sorted(i for i in wears if i not in before),
            "repeated_outfits": [
                {"item_ids": k.split("+"), "times": n} for k, n in outfits.most_common() if n > 1
            ],
            "posted_looks": sum(e.posted for e in month),
        }
    )


# ---------------- helpers for other modules (in-process) ----------------
def wear_log_for(user_id: str, since: dt.date | None = None) -> list[dict]:
    """[{date, item_ids, outfit_key, posted}] for M2 (rotation, forgotten pieces, remix novelty)."""
    res = history({"user_id": user_id, "payload": {"since": since, "limit": 5000}})["result"]["entries"]
    return [
        {
            "date": dt.date.fromisoformat(e["date"]),
            "item_ids": e["item_ids"],
            "outfit_key": e["outfit_key"],
            "posted": e["posted"],
        }
        for e in res
    ]


def unavailable_for(user_id: str) -> set[str]:
    return set(states({"user_id": user_id, "payload": {}})["result"]["unavailable"])


def has_data(user_id: str) -> bool:
    with storage.session() as s:
        return (
            s.scalars(select(WearEntryRow.entry_id).where(WearEntryRow.user_id == user_id).limit(1)).first()
            is not None
        )


def seed(user_id: str, log: list[dict]) -> int:
    """Bulk import of a past wear log [{date, item_ids}] (demo users, migration from another app)."""
    with storage.session() as s, s.begin():
        for e in log:
            ids = sorted(set(e["item_ids"]))
            if not ids:
                continue
            row = WearEntryRow(
                entry_id=uuid.uuid4().hex,
                user_id=user_id,
                date=e["date"],
                outfit_key=outfit_key(ids),
                posted=bool(e.get("posted")),
                source="import",
            )
            s.add(row)
            for i in ids:
                s.add(WearItemRow(entry_id=row.entry_id, item_id=i, user_id=user_id, date=e["date"]))
    return len(log)


def reset(user_id: str) -> None:
    with storage.session() as s, s.begin():
        for t in (WearItemRow, WearEntryRow, ItemStatusRow):
            s.execute(delete(t).where(t.user_id == user_id))
