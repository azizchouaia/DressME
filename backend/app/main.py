import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import api_router
from app.core.config import get_settings
from app.db.seed import ensure_demo_user
from app.db.session import SessionLocal

logger = logging.getLogger("smart_wardrobe")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if get_settings().seed_demo_user:
        try:
            with SessionLocal() as db:
                ensure_demo_user(db)
        except SQLAlchemyError:
            logger.exception("Could not seed demo user. Did you run `alembic upgrade head`?")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)

    if settings.storage_backend == "local":
        settings.storage_local_root.mkdir(parents=True, exist_ok=True)
        app.mount(
            settings.storage_public_base_url,
            StaticFiles(directory=settings.storage_local_root),
            name="media",
        )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
