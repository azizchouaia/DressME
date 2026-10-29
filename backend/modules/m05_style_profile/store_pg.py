"""M5 tables on PostgreSQL (+ pgvector). Same methods as repository.MemoryStore.

Created on the first call like M1's items table (the project has no Alembic migrations yet).
item_style.item_id refers to M1's items.item_id without a hard foreign key, so M5 keeps working when
M1 is mocked, and M1 stays free to delete its rows.
"""

import asyncio

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Integer,
    LargeBinary,
    String,
    Text,
    delete,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .bandit import LinearTS
from .repository import BanditRecord, LogRecord, LookRecord, ProfileRecord, now

EMBEDDING_DIM = 512
_JSON = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class StyleProfileRow(Base):
    __tablename__ = "style_profile"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    answers: Mapped[dict] = mapped_column(_JSON, default=dict)
    style_mix: Mapped[dict] = mapped_column(_JSON, default=dict)
    taste_vector = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    liked_sum = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    n_liked: Mapped[float] = mapped_column(Float, default=0.0)
    rejected_sum = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    n_rejected: Mapped[float] = mapped_column(Float, default=0.0)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.now())


class ItemStyleRow(Base):
    __tablename__ = "item_style"

    item_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    style_mix: Mapped[list] = mapped_column(_JSON)
    styles_version: Mapped[str] = mapped_column(String(40), index=True)


class BanditStateRow(Base):
    __tablename__ = "bandit_state"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dim: Mapped[int] = mapped_column(Integer)
    A: Mapped[bytes] = mapped_column(LargeBinary)
    b: Mapped[bytes] = mapped_column(LargeBinary)
    v: Mapped[float] = mapped_column(Float)
    prior_mean: Mapped[bytes] = mapped_column(LargeBinary)
    prior_strength: Mapped[float] = mapped_column(Float)
    n_updates: Mapped[int] = mapped_column(Integer, default=0)
    styles_version: Mapped[str] = mapped_column(String(40))
    updated_at = mapped_column(DateTime(timezone=True), server_default=func.now())


class BanditLogRow(Base):
    __tablename__ = "bandit_log"

    log_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    outfit_id: Mapped[str | None] = mapped_column(String(40), index=True)
    look_id: Mapped[str | None] = mapped_column(String(40))
    item_ids: Mapped[list] = mapped_column(_JSON, default=list)
    context: Mapped[dict] = mapped_column(_JSON)
    features = mapped_column(ARRAY(Float), nullable=False)
    shown_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    rank: Mapped[int | None] = mapped_column(Integer)
    score: Mapped[float | None] = mapped_column(Float)
    reward: Mapped[float | None] = mapped_column(Float)
    reaction: Mapped[str | None] = mapped_column(String(16))
    source: Mapped[str] = mapped_column(String(16))
    rewarded_at = mapped_column(DateTime(timezone=True), nullable=True)


class ReferenceLookRow(Base):
    __tablename__ = "reference_look"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    image_url: Mapped[str] = mapped_column(Text)
    style_id: Mapped[str] = mapped_column(String(40))
    family: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    formality: Mapped[float] = mapped_column(Float)
    warmth: Mapped[float] = mapped_column(Float)
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    version: Mapped[str] = mapped_column(String(64))


def _engine():
    from shared.db import engine  # lazy: creating the engine needs asyncpg

    return engine


def _sessions():
    from shared.db import SessionLocal

    return SessionLocal


def _log(r: BanditLogRow) -> LogRecord:
    return LogRecord(
        log_id=r.log_id,
        user_id=r.user_id,
        context=r.context,
        features=list(r.features),
        source=r.source,
        outfit_id=r.outfit_id,
        look_id=r.look_id,
        item_ids=list(r.item_ids or []),
        rank=r.rank,
        score=r.score,
        shown_at=r.shown_at,
        reward=r.reward,
        reaction=r.reaction,
        rewarded_at=r.rewarded_at,
    )


# columns added to style_profile after its first version (Rocchio taste)
_ADDED_COLUMNS = [
    ("liked_sum", f"vector({EMBEDDING_DIM})"),
    ("n_liked", "double precision DEFAULT 0"),
    ("rejected_sum", f"vector({EMBEDDING_DIM})"),
    ("n_rejected", "double precision DEFAULT 0"),
]


def _vec(v) -> list[float] | None:
    return None if v is None else [float(x) for x in v]


class PgStore:
    def __init__(self):
        self._ready = False
        self._lock = asyncio.Lock()

    async def ensure_schema(self) -> None:
        if self._ready:
            return
        async with self._lock:
            if self._ready:
                return
            async with _engine().begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                await conn.run_sync(Base.metadata.create_all)
                for col, kind in _ADDED_COLUMNS:  # create_all never alters an existing table
                    sql = f"ALTER TABLE style_profile ADD COLUMN IF NOT EXISTS {col} {kind}"
                    await conn.execute(text(sql))
            self._ready = True

    # profiles
    async def get_profile(self, user_id: str) -> ProfileRecord | None:
        await self.ensure_schema()
        async with _sessions()() as s:
            r = await s.get(StyleProfileRow, user_id)
            if r is None:
                return None
            return ProfileRecord(
                user_id=r.user_id,
                answers=dict(r.answers or {}),
                style_mix=dict(r.style_mix or {}),
                taste_vector=_vec(r.taste_vector),
                liked_sum=_vec(r.liked_sum),
                n_liked=r.n_liked or 0.0,
                rejected_sum=_vec(r.rejected_sum),
                n_rejected=r.n_rejected or 0.0,
                onboarded=r.onboarded,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )

    async def save_profile(self, p: ProfileRecord) -> ProfileRecord:
        await self.ensure_schema()
        p.created_at = p.created_at or now()
        p.updated_at = now()
        async with _sessions()() as s:
            await s.merge(
                StyleProfileRow(
                    user_id=p.user_id,
                    answers=p.answers,
                    style_mix=p.style_mix,
                    taste_vector=p.taste_vector,
                    liked_sum=p.liked_sum,
                    n_liked=p.n_liked,
                    rejected_sum=p.rejected_sum,
                    n_rejected=p.n_rejected,
                    onboarded=p.onboarded,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                )
            )
            await s.commit()
        return p

    async def delete_user(self, user_id: str) -> bool:
        await self.ensure_schema()
        async with _sessions()() as s:
            n = 0
            for model in (StyleProfileRow, BanditStateRow, BanditLogRow):
                n += (await s.execute(delete(model).where(model.user_id == user_id))).rowcount or 0
            await s.commit()
        return n > 0

    # item styles
    async def get_item_styles(self, item_ids: list[str], version: str) -> dict[str, list[float]]:
        if not item_ids:
            return {}
        await self.ensure_schema()
        async with _sessions()() as s:
            rows = (
                await s.execute(
                    select(ItemStyleRow.item_id, ItemStyleRow.style_mix).where(
                        ItemStyleRow.item_id.in_(item_ids), ItemStyleRow.styles_version == version
                    )
                )
            ).all()
        return {i: list(m) for i, m in rows}

    async def save_item_styles(self, mixes: dict[str, list[float]], version: str) -> None:
        if not mixes:
            return
        await self.ensure_schema()
        async with _sessions()() as s:
            for i, m in mixes.items():
                await s.merge(ItemStyleRow(item_id=i, style_mix=list(m), styles_version=version))
            await s.commit()

    async def drop_stale_item_styles(self, version: str) -> int:
        await self.ensure_schema()
        async with _sessions()() as s:
            n = (await s.execute(delete(ItemStyleRow).where(ItemStyleRow.styles_version != version))).rowcount
            await s.commit()
        return n or 0

    # bandit
    async def get_bandit(self, user_id: str) -> BanditRecord | None:
        await self.ensure_schema()
        async with _sessions()() as s:
            r = await s.get(BanditStateRow, user_id)
            if r is None:
                return None
            model = LinearTS.from_bytes(r.dim, r.A, r.b, r.prior_mean, r.prior_strength, r.v, r.n_updates)
            return BanditRecord(r.user_id, model, r.styles_version, r.updated_at)

    async def save_bandit(self, r: BanditRecord) -> None:
        await self.ensure_schema()
        r.updated_at = now()
        A, b, prior = r.model.to_bytes()
        async with _sessions()() as s:
            await s.merge(
                BanditStateRow(
                    user_id=r.user_id,
                    dim=r.model.dim,
                    A=A,
                    b=b,
                    v=r.model.v,
                    prior_mean=prior,
                    prior_strength=r.model.prior_strength,
                    n_updates=r.model.n_updates,
                    styles_version=r.styles_version,
                    updated_at=r.updated_at,
                )
            )
            await s.commit()

    # log
    async def add_logs(self, logs: list[LogRecord]) -> None:
        await self.ensure_schema()
        async with _sessions()() as s:
            for lg in logs:
                lg.shown_at = lg.shown_at or now()
                s.add(
                    BanditLogRow(
                        log_id=lg.log_id,
                        user_id=lg.user_id,
                        outfit_id=lg.outfit_id,
                        look_id=lg.look_id,
                        item_ids=lg.item_ids,
                        context=lg.context,
                        features=list(lg.features),
                        shown_at=lg.shown_at,
                        rank=lg.rank,
                        score=lg.score,
                        reward=lg.reward,
                        reaction=lg.reaction,
                        source=lg.source,
                        rewarded_at=lg.rewarded_at,
                    )
                )
            await s.commit()

    async def get_log(self, user_id: str, log_id: str) -> LogRecord | None:
        await self.ensure_schema()
        async with _sessions()() as s:
            r = await s.scalar(
                select(BanditLogRow).where(BanditLogRow.log_id == log_id, BanditLogRow.user_id == user_id)
            )
            return _log(r) if r else None

    async def find_open_log(
        self, user_id: str, outfit_id: str | None, look_id: str | None
    ) -> LogRecord | None:
        await self.ensure_schema()
        q = select(BanditLogRow).where(BanditLogRow.user_id == user_id, BanditLogRow.reward.is_(None))
        q = (
            q.where(BanditLogRow.outfit_id == outfit_id)
            if outfit_id
            else q.where(BanditLogRow.look_id == look_id)
        )
        async with _sessions()() as s:
            r = await s.scalar(q.order_by(BanditLogRow.shown_at.desc()).limit(1))
            return _log(r) if r else None

    async def set_reward(self, lg: LogRecord) -> None:
        await self.ensure_schema()
        async with _sessions()() as s:
            r = await s.get(BanditLogRow, lg.log_id)
            r.reward, r.reaction, r.source, r.rewarded_at = lg.reward, lg.reaction, lg.source, lg.rewarded_at
            await s.commit()

    async def count_feedback(self, user_id: str) -> int:
        await self.ensure_schema()
        async with _sessions()() as s:
            return int(
                await s.scalar(
                    select(func.count())
                    .select_from(BanditLogRow)
                    .where(BanditLogRow.user_id == user_id, BanditLogRow.reward.is_not(None))
                )
                or 0
            )

    # reference looks
    async def get_looks(self, version: str) -> list[LookRecord]:
        await self.ensure_schema()
        async with _sessions()() as s:
            rows = (
                await s.scalars(
                    select(ReferenceLookRow)
                    .where(ReferenceLookRow.version == version)
                    .order_by(ReferenceLookRow.id)
                )
            ).all()
        return [
            LookRecord(
                id=r.id,
                style_id=r.style_id,
                family=r.family,
                title=r.title,
                description=r.description,
                image_url=r.image_url,
                primary=r.is_primary,
                formality=r.formality,
                warmth=r.warmth,
                embedding=[float(x) for x in r.embedding],
                version=r.version,
            )
            for r in rows
        ]

    async def save_looks(self, looks: list[LookRecord]) -> None:
        await self.ensure_schema()
        async with _sessions()() as s:
            await s.execute(delete(ReferenceLookRow))
            for lk in looks:
                s.add(
                    ReferenceLookRow(
                        id=lk.id,
                        image_url=lk.image_url,
                        style_id=lk.style_id,
                        family=lk.family,
                        title=lk.title,
                        description=lk.description,
                        is_primary=lk.primary,
                        formality=lk.formality,
                        warmth=lk.warmth,
                        embedding=lk.embedding,
                        version=lk.version,
                    )
                )
            await s.commit()
