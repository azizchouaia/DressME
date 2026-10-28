"""Async SQLAlchemy engine/session. Tables are defined in shared/models_db.py.

NullPool: every session opens its own connection. Some agents call M1 from synchronous code through
asyncio.run in a worker thread (another event loop); a pooled asyncpg connection belongs to the loop
that created it and fails there ("attached to a different loop"). Without a pool that cannot happen.
"""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from shared.config import settings

engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
