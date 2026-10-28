"""Item table (PostgreSQL + pgvector). Every query is filtered by user_id.

The table is `items`: the columns of shared.schemas.Garment + `embedding VECTOR(512)` + `status` +
`price_tnd`. Extension, table and HNSW index are created on the first call (no migration yet).
"""

import asyncio
from collections.abc import Sequence

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Date, DateTime, Float, Index, Integer, String, Text, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, aliased, mapped_column

from .contract import EMBEDDING_DIM, ItemsRequest, SimilarItem, WardrobeItem

_JSON = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class ItemRow(Base):
    __tablename__ = "items"

    item_id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    image_raw: Mapped[str] = mapped_column(Text)
    image_cutout: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(20), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(64))
    colors: Mapped[list] = mapped_column(_JSON, default=list)
    pattern: Mapped[str | None] = mapped_column(String(32))
    material: Mapped[str | None] = mapped_column(String(32))
    season: Mapped[list] = mapped_column(_JSON, default=list)
    formality: Mapped[float | None] = mapped_column(Float)
    local_tag: Mapped[str | None] = mapped_column(String(32))
    embedding_id: Mapped[str | None] = mapped_column(String(40))
    confidence: Mapped[float | None] = mapped_column(Float)
    wear_count: Mapped[int] = mapped_column(Integer, default=0)
    last_worn = mapped_column(Date, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    price_tnd: Mapped[float | None] = mapped_column(Float)
    # details added by the user (form) or extracted from a receipt / label
    brand: Mapped[str | None] = mapped_column(String(80))
    size: Mapped[str | None] = mapped_column(String(20))
    size_system: Mapped[str | None] = mapped_column(String(16))
    reference: Mapped[str | None] = mapped_column(String(60))
    purchase_date = mapped_column(Date, nullable=True)
    purchase_year: Mapped[int | None] = mapped_column(Integer)
    store: Mapped[str | None] = mapped_column(String(120))
    store_id: Mapped[str | None] = mapped_column(String(64))
    composition: Mapped[list] = mapped_column(_JSON, default=list)
    care: Mapped[list] = mapped_column(_JSON, default=list)
    condition: Mapped[str | None] = mapped_column(String(16))
    notes: Mapped[str | None] = mapped_column(Text)
    receipt_image: Mapped[str | None] = mapped_column(Text)
    donated_at = mapped_column(DateTime(timezone=True), nullable=True)
    donation_place: Mapped[str | None] = mapped_column(String(16))
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=False)

    __table_args__ = (
        Index(
            "ix_items_embedding_hnsw", "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


_FIELDS = tuple(WardrobeItem.model_fields)

# Columns added after the first version of the table: `create_all` does not alter an existing table,
# so they are added here (idempotent) until the project has Alembic migrations.
_ADDED_COLUMNS = {
    "brand": "VARCHAR(80)", "size": "VARCHAR(20)", "size_system": "VARCHAR(16)", "reference": "VARCHAR(60)",
    "purchase_date": "DATE", "purchase_year": "INTEGER", "store": "VARCHAR(120)", "store_id": "VARCHAR(64)",
    "composition": "JSONB DEFAULT '[]'::jsonb", "care": "JSONB DEFAULT '[]'::jsonb",
    "condition": "VARCHAR(16)", "notes": "TEXT", "receipt_image": "TEXT",
    "donated_at": "TIMESTAMPTZ", "donation_place": "VARCHAR(16)",
}

_ready = False
_lock = asyncio.Lock()


def _engine():
    from shared.db import engine  # lazy: creating the engine needs asyncpg

    return engine


def _sessions():
    from shared.db import SessionLocal

    return SessionLocal


async def ensure_schema() -> None:
    global _ready
    if _ready:
        return
    async with _lock:
        if _ready:
            return
        async with _engine().begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
            for column, ddl in _ADDED_COLUMNS.items():
                await conn.execute(text(f"ALTER TABLE items ADD COLUMN IF NOT EXISTS {column} {ddl}"))
        _ready = True


def _to_item(row: ItemRow) -> WardrobeItem:
    return WardrobeItem.model_validate({f: getattr(row, f) for f in _FIELDS})


async def add_item(item: WardrobeItem, embedding: Sequence[float]) -> WardrobeItem:
    data = item.model_dump(mode="json", exclude={"shelf", "created_at", "last_worn", "purchase_date",
                                                 "donated_at"})
    row = ItemRow(**data, last_worn=item.last_worn, purchase_date=item.purchase_date,
                  donated_at=item.donated_at, embedding=list(embedding))
    async with _sessions()() as s:
        s.add(row)
        await s.commit()
        await s.refresh(row)
        return _to_item(row)


async def get_item(user_id: str, item_id: str) -> WardrobeItem | None:
    async with _sessions()() as s:
        row = await s.scalar(select(ItemRow).where(ItemRow.user_id == user_id, ItemRow.item_id == item_id))
        return _to_item(row) if row else None


async def get_embedding(user_id: str, item_id: str) -> list[float] | None:
    async with _sessions()() as s:
        vec = await s.scalar(
            select(ItemRow.embedding).where(ItemRow.user_id == user_id, ItemRow.item_id == item_id)
        )
        return None if vec is None else [float(v) for v in vec]


async def get_embeddings(user_id: str, item_ids: Sequence[str] | None = None) -> dict[str, list[float]]:
    """item_id -> embedding of the user's non-pending items; all of them when item_ids is None."""
    q = select(ItemRow.item_id, ItemRow.embedding).where(
        ItemRow.user_id == user_id, ItemRow.status != "pending")
    if item_ids is not None:
        q = q.where(ItemRow.item_id.in_(list(item_ids)))
    async with _sessions()() as s:
        rows = (await s.execute(q)).all()
    return {i: [float(v) for v in vec] for i, vec in rows}


async def list_items(req: ItemsRequest) -> list[WardrobeItem]:
    q = select(ItemRow).where(ItemRow.user_id == req.user_id)
    if req.category:
        q = q.where(ItemRow.category == req.category.value)
    if req.status:
        q = q.where(ItemRow.status == req.status.value)
    else:                       # pending: waiting for the user; donated: in the "À donner" bag
        q = q.where(ItemRow.status.not_in(("pending", "donated")))
    if req.season:
        q = q.where(ItemRow.season.op("@>")(func.jsonb_build_array(req.season.lower())))
    if req.color:
        wanted = func.jsonb_build_array(func.jsonb_build_object("name", req.color.lower()))
        q = q.where(ItemRow.colors.op("@>")(wanted))
    async with _sessions()() as s:
        rows = (await s.scalars(q.order_by(ItemRow.created_at, ItemRow.item_id))).all()
        return [_to_item(r) for r in rows]


async def set_status(user_id: str, item_id: str, from_status: str, to_status: str) -> WardrobeItem | None:
    """Moves an item from `from_status` to `to_status`; None when there is no such item in that status."""
    async with _sessions()() as s:
        row = await s.scalar(select(ItemRow).where(
            ItemRow.user_id == user_id, ItemRow.item_id == item_id, ItemRow.status == from_status))
        if row is None:
            return None
        row.status = to_status
        await s.commit()
        await s.refresh(row)
        return _to_item(row)


async def update_item(user_id: str, item_id: str, values: dict) -> WardrobeItem | None:
    """Writes the given columns (already validated, see details.to_db); None when the item is unknown."""
    async with _sessions()() as s:
        row = await s.scalar(select(ItemRow).where(ItemRow.user_id == user_id, ItemRow.item_id == item_id))
        if row is None:
            return None
        for key, value in values.items():
            setattr(row, key, value)
        await s.commit()
        await s.refresh(row)
        return _to_item(row)


async def delete_item(user_id: str, item_id: str) -> bool:
    async with _sessions()() as s:
        row = await s.scalar(select(ItemRow).where(ItemRow.user_id == user_id, ItemRow.item_id == item_id))
        if row is None:
            return False
        await s.delete(row)
        await s.commit()
        return True


async def nearest(
    user_id: str, vector: Sequence[float], k: int, min_similarity: float, exclude_id: str | None = None
) -> list[SimilarItem]:
    """k nearest active items of this user (HNSW cosine), keeping similarity >= min_similarity."""
    dist = ItemRow.embedding.cosine_distance(list(vector))
    q = select(ItemRow.item_id, dist.label("d")).where(ItemRow.user_id == user_id, ItemRow.status == "active")
    if exclude_id:
        q = q.where(ItemRow.item_id != exclude_id)
    async with _sessions()() as s:
        rows = (await s.execute(q.order_by(dist).limit(k))).all()
    out = [SimilarItem(item_id=i, similarity=round(max(-1.0, min(1.0, 1 - float(d))), 4)) for i, d in rows]
    return [n for n in out if n.similarity >= min_similarity]


async def duplicate_pairs(user_id: str, threshold: float) -> list[tuple[str, str]]:
    """Pairs of active items of this user with cosine similarity > threshold (self-join)."""
    a, b = aliased(ItemRow), aliased(ItemRow)
    q = (
        select(a.item_id, b.item_id)
        .join(b, (a.user_id == b.user_id) & (a.item_id < b.item_id))
        .where(a.user_id == user_id, a.status == "active", b.status == "active")
        .where(a.embedding.cosine_distance(b.embedding) < 1 - threshold)
    )
    async with _sessions()() as s:
        return [(x, y) for x, y in (await s.execute(q)).all()]
