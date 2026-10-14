"""M3 tables (SQLAlchemy 2.0, sync). SQLite file by default, Postgres in docker / prod:

    M03_DATABASE_URL=postgresql+psycopg2://dressme:change_me@localhost:5432/dressme

Tables are created on first use. They are owned by M3 (prefix m03_); other modules call the API.
"""

from __future__ import annotations

import datetime as dt
import os
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Boolean, Date, DateTime, Integer, String, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DEFAULT_SQLITE = Path(__file__).parent / ".data" / "m03.sqlite"


class Base(DeclarativeBase):
    pass


class WearEntryRow(Base):
    """One "worn" event: a set of pieces worn together on a day."""

    __tablename__ = "m03_wear_entries"
    entry_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    outfit_key: Mapped[str] = mapped_column(String(1024), index=True)
    outfit_id: Mapped[str | None] = mapped_column(String(64))
    posted: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


class WearItemRow(Base):
    """Pieces of an entry (one row per piece, for per-item queries)."""

    __tablename__ = "m03_wear_items"
    entry_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)


class ItemStatusRow(Base):
    """Current status of a piece. No row = available, never washed-counted."""

    __tablename__ = "m03_item_status"
    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="available")
    since: Mapped[dt.date | None] = mapped_column(Date)
    lent_to: Mapped[str | None] = mapped_column(String(128))
    expected_back: Mapped[dt.date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(256))
    wears_since_wash: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)


def database_url() -> str:
    url = os.environ.get("M03_DATABASE_URL")
    if url:
        return url
    DEFAULT_SQLITE.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_SQLITE.as_posix()}"


@lru_cache(maxsize=4)
def _factory(url: str) -> sessionmaker[Session]:
    engine = create_engine(url, future=True)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _pragmas(conn, _):  # concurrent readers while the API writes
            conn.execute("PRAGMA journal_mode=WAL")

    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


def session() -> Session:
    return _factory(database_url())()
