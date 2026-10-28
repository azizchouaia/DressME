"""PgStore against a real PostgreSQL + pgvector (same methods as MemoryStore).

Skipped unless M05_TEST_DATABASE_URL (or M01_TEST_DATABASE_URL) is set, e.g.
    M05_TEST_DATABASE_URL=postgresql+asyncpg://dressme:change_me@localhost:5432/dressme
Each test uses its own user / item ids and deletes its rows afterwards.
"""

import os
import uuid

import numpy as np
import pytest
from sqlalchemy import text

from modules.m05_style_profile import store_pg
from modules.m05_style_profile.bandit import LinearTS
from modules.m05_style_profile.repository import (
    BanditRecord,
    LogRecord,
    LookRecord,
    ProfileRecord,
    new_log_id,
)

URL = os.environ.get("M05_TEST_DATABASE_URL") or os.environ.get("M01_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL, reason="set M05_TEST_DATABASE_URL to run the PostgreSQL tests")


@pytest.fixture
async def pg(monkeypatch):
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    engine = create_async_engine(URL)
    monkeypatch.setattr(store_pg, "_engine", lambda: engine)
    monkeypatch.setattr(store_pg, "_sessions", lambda: async_sessionmaker(engine, expire_on_commit=False))
    user = f"test_{uuid.uuid4().hex[:10]}"
    yield store_pg.PgStore(), user
    async with engine.begin() as conn:
        for table in ("style_profile", "bandit_state", "bandit_log"):
            await conn.execute(text(f"DELETE FROM {table} WHERE user_id = :u"), {"u": user})
        await conn.execute(text("DELETE FROM item_style WHERE item_id LIKE :u"), {"u": f"{user}%"})
    await engine.dispose()


def unit(n: int) -> list[float]:
    v = np.zeros(512)
    v[n] = 1
    return v.tolist()


async def test_profile_round_trip(pg):
    store, user = pg
    assert await store.get_profile(user) is None
    p = ProfileRecord(
        user_id=user,
        answers={"_onboarding_open": ["lg_a"]},
        style_mix={"classic": 0.6},
        taste_vector=unit(3),
        liked_sum=unit(3),
        n_liked=1.0,
        rejected_sum=unit(4),
        n_rejected=0.5,
    )
    await store.save_profile(p)
    p.answers = {"want_more": ["classic"]}
    p.onboarded = True
    await store.save_profile(p)  # upsert
    back = await store.get_profile(user)
    assert back.answers == {"want_more": ["classic"]} and back.style_mix == {"classic": 0.6}
    assert back.taste_vector[3] == 1.0 and back.onboarded
    assert back.liked_sum[3] == 1.0 and back.rejected_sum[4] == 1.0
    assert (back.n_liked, back.n_rejected) == (1.0, 0.5)
    assert back.created_at is not None
    assert await store.delete_user(user) and await store.get_profile(user) is None


async def test_bandit_round_trip_bytea(pg):
    store, user = pg
    rng = np.random.default_rng(0)
    m = LinearTS(90, rng.standard_normal(90), prior_strength=2.0, v=0.3)
    m.update(rng.standard_normal(90), 1.0)
    await store.save_bandit(BanditRecord(user, m, "v1"))
    back = await store.get_bandit(user)
    np.testing.assert_array_equal(back.model.A, m.A)
    np.testing.assert_array_equal(back.model.b, m.b)
    np.testing.assert_array_equal(back.model.prior_mean, m.prior_mean)
    assert back.styles_version == "v1" and back.model.n_updates == 1


async def test_log_and_rewards(pg):
    store, user = pg
    a = LogRecord(
        log_id=new_log_id(),
        user_id=user,
        context={"temp_c": 20},
        features=[1.0, 0.5],
        source="swipe",
        outfit_id="out_x",
        item_ids=["i1"],
        rank=0,
        score=0.3,
    )
    await store.add_logs([a])
    assert (await store.find_open_log(user, "out_x", None)).log_id == a.log_id
    a.reward, a.reaction = 1.0, "heart"
    await store.set_reward(a)
    got = await store.get_log(user, a.log_id)
    assert got.reward == 1.0 and got.features == [1.0, 0.5] and got.item_ids == ["i1"]
    assert await store.find_open_log(user, "out_x", None) is None
    assert await store.count_feedback(user) == 1
    assert await store.get_log("someone_else", a.log_id) is None


async def test_item_styles_versions(pg):
    store, user = pg
    await store.save_item_styles({f"{user}_a": [0.7, 0.3], f"{user}_b": [0.1, 0.9]}, "v1")
    assert await store.get_item_styles([f"{user}_a", f"{user}_b"], "v2") == {}
    assert (await store.get_item_styles([f"{user}_a"], "v1"))[f"{user}_a"] == [0.7, 0.3]
    assert await store.drop_stale_item_styles("v2") >= 2


async def test_reference_looks(pg):
    store, _ = pg
    look = LookRecord(
        id="look_test",
        style_id="classic",
        family="elegant",
        title="T",
        description="d",
        image_url="/x.svg",
        primary=True,
        formality=0.8,
        warmth=0.5,
        embedding=unit(1),
        version="test",
    )
    await store.save_looks([look])
    back = await store.get_looks("test")
    assert len(back) == 1 and back[0].embedding[1] == 1.0 and back[0].primary
    assert await store.get_looks("other") == []
    await store.save_looks([])
