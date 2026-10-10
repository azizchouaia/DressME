"""Async SQLAlchemy engine/session. Tables are defined in shared/models_db.py."""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from shared.config import settings

engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
