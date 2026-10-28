"""Integration tests against a real PostgreSQL + pgvector.

Skipped unless M01_TEST_DATABASE_URL is set, e.g.
    M01_TEST_DATABASE_URL=postgresql+asyncpg://dressme:change_me@localhost:5432/dressme
Each test uses its own user ids and deletes its rows afterwards.
"""

import os
import uuid

import numpy as np
import pytest
from sqlalchemy import text

from modules.m01_wardrobe import service, store
from modules.m01_wardrobe.contract import (
    EMBEDDING_DIM,
    ClassifyRequest,
    DuplicatesRequest,
    ItemNotFoundError,
    ItemsRequest,
    ItemStatus,
    ItemUpdate,
    SimilarRequest,
    WardrobeItem,
)
from shared.schemas import Color, GarmentCategory

from .helpers import png_b64
from .test_service import fake_analysis

URL = os.environ.get("M01_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="set M01_TEST_DATABASE_URL to run the pgvector tests")


@pytest.fixture
async def db(monkeypatch):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(URL)
    monkeypatch.setattr(store, "_engine", lambda: engine)
    monkeypatch.setattr(store, "_sessions", lambda: async_sessionmaker(engine, expire_on_commit=False))
    monkeypatch.setattr(store, "_ready", False)
    users: list[str] = []

    def new_user() -> str:
        users.append(f"test_{uuid.uuid4().hex[:10]}")
        return users[-1]

    yield new_user, engine
    async with engine.begin() as conn:
        for u in users:
            await conn.execute(text("DELETE FROM items WHERE user_id = :u"), {"u": u})
    await engine.dispose()


def unit(v) -> list[float]:
    v = np.asarray(v, dtype=np.float64)
    return list(v / np.linalg.norm(v))


def basis(i: int, j: int | None = None, w: float = 0.0) -> list[float]:
    """Unit vector e_i, optionally tilted towards e_j (cosine with e_i = 1/sqrt(1 + w^2))."""
    v = np.zeros(EMBEDDING_DIM)
    v[i] = 1
    if j is not None:
        v[j] = w
    return unit(v)


def item(user: str, item_id: str, category=GarmentCategory.top, **kw) -> WardrobeItem:
    return WardrobeItem(item_id=item_id, user_id=user, image_raw=f"/m01/media/{user}/{item_id}.png",
                        category=category, embedding_id=item_id, **kw)


async def test_schema_extension_table_and_hnsw_index(db):
    _, engine = db
    await store.ensure_schema()
    async with engine.connect() as conn:
        assert await conn.scalar(text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
        idx = await conn.scalar(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_items_embedding_hnsw'"))
    assert "hnsw" in idx and "vector_cosine_ops" in idx


async def test_crud_filters_and_user_isolation(db):
    new_user, _ = db
    u, other = new_user(), new_user()
    await store.ensure_schema()
    await store.add_item(item(u, f"{u}_shirt", season=["summer"], price_tnd=89,
                              colors=[Color(name="navy", hex="#1F2A44", share=0.9)]), basis(0))
    await store.add_item(item(u, f"{u}_boots", GarmentCategory.shoes, season=["winter"],
                              status=ItemStatus.archived), basis(1))
    await store.add_item(item(other, f"{other}_shirt"), basis(0))

    got = await store.get_item(u, f"{u}_shirt")
    assert got.price_tnd == 89 and got.colors[0].name == "navy" and got.created_at is not None
    assert await store.get_item(other, f"{u}_shirt") is None                    # never another user's
    np.testing.assert_allclose(await store.get_embedding(u, f"{u}_shirt"), basis(0), atol=1e-6)

    ids = lambda items: {i.item_id for i in items}                               # noqa: E731
    assert ids(await store.list_items(ItemsRequest(user_id=u))) == {f"{u}_shirt", f"{u}_boots"}
    assert ids(await store.list_items(ItemsRequest(user_id=u, category="shoes"))) == {f"{u}_boots"}
    assert ids(await store.list_items(ItemsRequest(user_id=u, season="summer"))) == {f"{u}_shirt"}
    assert ids(await store.list_items(ItemsRequest(user_id=u, color="Navy"))) == {f"{u}_shirt"}
    assert ids(await store.list_items(ItemsRequest(user_id=u, status="archived"))) == {f"{u}_boots"}

    assert await store.delete_item(u, f"{u}_boots") is True
    assert await store.delete_item(u, f"{u}_boots") is False


async def test_nearest_and_duplicate_pairs(db):
    new_user, _ = db
    u, other = new_user(), new_user()
    await store.ensure_schema()
    # a ~ a2 (cos 0.98), a ~ a3 (cos 0.8), b alone, archived copy of a ignored, other user's copy ignored
    await store.add_item(item(u, f"{u}_a"), basis(0))
    await store.add_item(item(u, f"{u}_a2"), basis(0, 5, 0.2))
    await store.add_item(item(u, f"{u}_a3"), basis(0, 6, 0.75))
    await store.add_item(item(u, f"{u}_b"), basis(1))
    await store.add_item(item(u, f"{u}_old", status=ItemStatus.archived), basis(0))
    await store.add_item(item(other, f"{other}_a"), basis(0))

    near = await store.nearest(u, basis(0), k=5, min_similarity=0.75, exclude_id=f"{u}_a")
    assert [n.item_id for n in near] == [f"{u}_a2", f"{u}_a3"]
    assert near[0].similarity == pytest.approx(0.9806, abs=1e-3)
    assert near[1].similarity == pytest.approx(0.8, abs=1e-3)
    assert len(await store.nearest(u, basis(0), k=1, min_similarity=0)) == 1

    pairs = await store.duplicate_pairs(u, 0.85)
    assert pairs == [(f"{u}_a", f"{u}_a2")]


async def test_details_columns_and_update(db):
    new_user, engine = db
    u = new_user()
    await store.ensure_schema()
    async with engine.connect() as conn:
        cols = {r[0] for r in await conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'items'"))}
    assert {"brand", "size", "purchase_date", "composition", "care", "receipt_image"} <= cols

    await store.add_item(item(u, f"{u}_chino", GarmentCategory.bottom, subcategory="chinos"), basis(3))
    update = ItemUpdate(size="40", size_system="eu", brand="Zara", price_tnd=119.9,
                        purchase_date="2026-09-14",
                        composition=[{"material": "coton", "percent": 100}], care=["30 °C"], condition="good")
    out = await service.update_item(u, f"{u}_chino", update)
    again = await store.get_item(u, f"{u}_chino")
    for got in (out, again):
        assert (got.size, got.size_system, got.brand, got.price_tnd) == ("40", "eu", "Zara", 119.9)
        assert got.purchase_date.isoformat() == "2026-09-14" and got.purchase_year == 2026
        assert got.composition[0].material == "coton" and got.care == ["30 °C"] and got.condition == "good"
    cleared = await service.update_item(u, f"{u}_chino", ItemUpdate(brand=None, care=None))
    assert cleared.brand is None and cleared.care == [] and cleared.size == "40"


async def test_hnsw_index_is_usable(db):
    _, engine = db
    await store.ensure_schema()
    q = "[" + ",".join(["0"] * (EMBEDDING_DIM - 1) + ["1"]) + "]"
    async with engine.connect() as conn:
        await conn.execute(text("SET enable_seqscan = off"))
        plan = "\n".join(r[0] for r in await conn.execute(
            text(f"EXPLAIN SELECT item_id FROM items ORDER BY embedding <=> '{q}' LIMIT 5")))
    assert "ix_items_embedding_hnsw" in plan


async def test_service_end_to_end_with_fake_models(db, monkeypatch):
    """service.py + real pgvector; only the models are replaced."""
    new_user, _ = db
    u = new_user()
    monkeypatch.setattr(service, "_analyse", lambda data, full=True: fake_analysis())

    first = await service.classify(ClassifyRequest(user_id=u, image=png_b64(), price_tnd=89))
    assert first.stored and first.duplicates == []
    second = await service.classify(ClassifyRequest(user_id=u, image=png_b64()))
    assert [d.item_id for d in second.duplicates] == [first.garment.item_id]   # same embedding
    assert second.pending and not second.stored                                # held for the user
    assert (await service.items(ItemsRequest(user_id=u))).total == 1           # hidden while pending
    assert (await service.duplicates(DuplicatesRequest(user_id=u))).groups == []
    assert (await service.confirm_item(u, second.garment.item_id)).status == "active"

    listed = await service.items(ItemsRequest(user_id=u))
    assert listed.total == 2
    sim = await service.similar(SimilarRequest(user_id=u, item_id=first.garment.item_id))
    assert [n.item_id for n in sim.neighbours] == [second.garment.item_id]
    groups = (await service.duplicates(DuplicatesRequest(user_id=u))).groups
    assert groups == [sorted([first.garment.item_id, second.garment.item_id])]

    assert (await service.get_item(u, first.garment.item_id)).price_tnd == 89
    assert (await service.delete_item(u, first.garment.item_id)).deleted
    with pytest.raises(ItemNotFoundError):
        await service.get_item(u, first.garment.item_id)


async def test_embeddings_bulk_read(db, monkeypatch):
    new_user, _ = db
    u = new_user()
    monkeypatch.setattr(service, "_analyse", lambda data, full=True: fake_analysis())
    first = await service.classify(ClassifyRequest(user_id=u, image=png_b64()))
    pending = await service.classify(ClassifyRequest(user_id=u, image=png_b64()))     # duplicate -> pending
    assert pending.pending
    out = await service.embeddings(u)
    assert list(out) == [first.garment.item_id] and len(out[first.garment.item_id]) == EMBEDDING_DIM
    assert await service.embeddings(u, ["nope"]) == {}


async def test_donate_with_pgvector(db, monkeypatch):
    from modules.m01_wardrobe.contract import DonateRequest, DonationPlace

    new_user, _ = db
    u = new_user()
    monkeypatch.setattr(service, "_analyse", lambda data, full=True: fake_analysis())
    item = (await service.classify(ClassifyRequest(user_id=u, image=png_b64()))).garment
    out = await service.donate_item(u, item.item_id, DonateRequest(place=DonationPlace.friend))
    assert out.status == "donated" and out.donation_place == "friend" and out.donated_at is not None
    assert (await service.items(ItemsRequest(user_id=u))).total == 0
    assert (await service.items(ItemsRequest(user_id=u, status=ItemStatus.donated))).total == 1
