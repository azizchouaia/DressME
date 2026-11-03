import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.api.router import api_router
from app.core.config import REPO_ROOT, get_settings
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
    # Flutter web runs on its own localhost port. Mobile apps are not subject to CORS.
    cors_kwargs: dict[str, object] = {
        "allow_origins": settings.cors_origins,
        "allow_credentials": True,
        "allow_methods": ["*"],
        "allow_headers": ["*"],
    }
    if settings.environment == "development":
        cors_kwargs["allow_origin_regex"] = r"https?://(localhost|127\.0\.0\.1)(:\d+)?$"
    app.add_middleware(CORSMiddleware, **cors_kwargs)
    app.include_router(api_router, prefix=settings.api_prefix)

    if settings.storage_backend == "local":
        settings.storage_local_root.mkdir(parents=True, exist_ok=True)
        app.mount(
            settings.storage_public_base_url,
            StaticFiles(directory=settings.storage_local_root),
            name="media",
        )

    models_dir = REPO_ROOT / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/models", StaticFiles(directory=models_dir), name="models")

    viewer_dir = REPO_ROOT / "viewer"
    if viewer_dir.is_dir():
        app.mount("/viewer", StaticFiles(directory=viewer_dir, html=True), name="viewer")

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
