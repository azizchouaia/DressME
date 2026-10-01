from functools import lru_cache

from app.core.config import get_settings
from app.services.storage.base import StorageService
from app.services.storage.local import LocalStorage


@lru_cache
def get_storage() -> StorageService:
    settings = get_settings()
    if settings.storage_backend == "s3":
        from app.services.storage.s3 import S3Storage

        if not settings.storage_bucket:
            raise RuntimeError("STORAGE_BUCKET is required when STORAGE_BACKEND=s3")
        return S3Storage(
            bucket=settings.storage_bucket,
            endpoint_url=settings.storage_endpoint,
            access_key=settings.storage_access_key,
            secret_key=settings.storage_secret_key,
            region=settings.storage_region,
            public_base_url=settings.storage_public_base_url,
        )
    return LocalStorage(settings.storage_local_root, settings.storage_public_base_url)


__all__ = ["StorageService", "get_storage"]
