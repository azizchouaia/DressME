from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Smart Wardrobe API"
    api_prefix: str = "/api/v1"
    environment: Literal["development", "test", "production"] = "development"

    database_url: str = "postgresql+psycopg://wardrobe:wardrobe@localhost:5432/smart_wardrobe"

    secret_key: str = "dev-only-change-me"
    access_token_expire_minutes: int = 60 * 24 * 7

    cors_origins: list[str] = ["http://localhost:5287", "http://127.0.0.1:5287"]

    storage_backend: Literal["local", "s3"] = "local"
    storage_local_root: Path = REPO_ROOT / "storage"
    storage_public_base_url: str = "/media"
    storage_endpoint: str | None = None
    storage_bucket: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: str | None = None
    storage_region: str = "auto"

    clothing_analyzer: Literal["local-heuristic"] = "local-heuristic"

    seed_demo_user: bool = True
    demo_email: str = "demo@smartwardrobe.app"
    demo_password: str = "try-the-wardrobe"
    demo_name: str = "Nadhir"


@lru_cache
def get_settings() -> Settings:
    return Settings()
