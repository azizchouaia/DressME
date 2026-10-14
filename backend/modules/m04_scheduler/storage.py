"""M4 tables (SQLAlchemy 2.0, sync). SQLite file by default, Postgres in docker / prod:

M04_DATABASE_URL=postgresql+psycopg2://dressme:change_me@localhost:5432/dressme
"""

from __future__ import annotations

import datetime as dt
import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy import JSON, Boolean, Date, DateTime, Integer, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DEFAULT_SQLITE = Path(__file__).parent / ".data" / "m04.sqlite"


def _now() -> dt.datetime:
    return dt.datetime.now(dt.UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class PrefsRow(Base):
    """Scheduling preferences of a user. A row = the user is scheduled."""

    __tablename__ = "m04_prefs"
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    city: Mapped[str] = mapped_column(String(64), default="Tunis")
    timezone: Mapped[str] = mapped_column(String(64), default="Africa/Tunis")
    morning_time: Mapped[str] = mapped_column(String(5), default="05:00")  # compute today's outfit
    notify_time: Mapped[str] = mapped_column(String(5), default="07:00")  # push it
    evening_time: Mapped[str] = mapped_column(String(5), default="20:00")  # tomorrow's outfit + tips
    weekday_occasions: Mapped[list] = mapped_column(JSON)  # 7 occasions, Monday first
    jobs: Mapped[dict] = mapped_column(JSON)  # job name -> enabled
    push_token: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class EventRow(Base):
    __tablename__ = "m04_events"
    event_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(128))
    occasion: Mapped[str] = mapped_column(String(16), default="event")
    dress_code: Mapped[str | None] = mapped_column(String(128))
    notes: Mapped[str | None] = mapped_column(String(512))
    remind_days: Mapped[int] = mapped_column(Integer, default=5)  # shortlist this many days before
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class OutfitCacheRow(Base):
    """Precomputed outfits: kind "day" (outfit of a day) or "event:<id>" (event shortlist)."""

    __tablename__ = "m04_outfits"
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    kind: Mapped[str] = mapped_column(String(48), primary_key=True)
    result: Mapped[dict] = mapped_column(JSON)  # M2 result: outfits (options), items, context
    choice: Mapped[int] = mapped_column(Integer, default=0)  # option shown (Change -> next)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)  # locked: not recomputed in the morning
    occasion: Mapped[str] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(32))  # morning / evening / event / week / on_demand
    computed_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)


class NotificationRow(Base):
    """Notification outbox. The app reads it (or a push sender delivers it when configured)."""

    __tablename__ = "m04_notifications"
    notif_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(128))
    body: Mapped[str] = mapped_column(String(512))
    data: Mapped[dict] = mapped_column(JSON)
    actions: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="unread")  # unread / read / acted
    action_taken: Mapped[str | None] = mapped_column(String(32))
    delivered: Mapped[str] = mapped_column(String(32), default="outbox")  # outbox / fcm / failed
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, index=True)


class JobRunRow(Base):
    """One row per job that ran for a user on a local day: the scheduler never runs a job twice."""

    __tablename__ = "m04_job_runs"
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_key: Mapped[str] = mapped_column(String(64), primary_key=True)  # e.g. "morning:2026-10-14"
    ran_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    summary: Mapped[str | None] = mapped_column(String(256))


def database_url() -> str:
    url = os.environ.get("M04_DATABASE_URL")
    if url:
        return url
    DEFAULT_SQLITE.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_SQLITE.as_posix()}"


@lru_cache(maxsize=4)
def _factory(url: str) -> sessionmaker[Session]:
    engine = create_engine(url, future=True)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _pragmas(conn, _):
            conn.execute("PRAGMA journal_mode=WAL")

    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def session() -> Session:
    return _factory(database_url())()
