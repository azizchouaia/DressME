"""Image storage for M1.

- `local` (default): files under `data/media/<user>/`, served by `GET /m01/media/...` (git-ignored).
- `s3` (M01_STORAGE=s3): `shared.storage.upload_bytes`. It returns `s3://` URIs that a browser cannot
  display until shared/storage.py exposes presigned URLs (see README, "outside M1").
"""

import hashlib
import re

from .config import data_dir, storage_backend

MEDIA_URL = "/m01/media"
_UNSAFE = re.compile(r"[^A-Za-z0-9_-]")


def safe_part(value: str) -> str:
    cleaned = _UNSAFE.sub("_", value)[:64]
    return cleaned if cleaned.strip("_") else hashlib.sha1(value.encode()).hexdigest()[:16]


def media_root():
    return data_dir() / "media"


def save_image(user_id: str, item_id: str, kind: str, data: bytes, ext: str = "png") -> str:
    """Store one image (`kind` = raw | cutout) and return the URL / URI to put in Garment."""
    user, name = safe_part(user_id), f"{safe_part(item_id)}_{kind}.{ext}"
    if storage_backend() == "s3":
        from shared.storage import upload_bytes

        content_type = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        return upload_bytes(f"m01/{user}/{name}", data, content_type)
    folder = media_root() / user
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(data)
    return f"{MEDIA_URL}/{user}/{name}"


def delete_image(user_id: str, item_id: str, kind: str) -> None:
    """Deletes one image of an item (e.g. the receipt when the user no longer wants to keep it)."""
    if storage_backend() == "s3":
        return
    folder = media_root() / safe_part(user_id)
    for path in folder.glob(f"{safe_part(item_id)}_{kind}.*"):
        path.unlink(missing_ok=True)


def delete_images(user_id: str, item_id: str) -> None:
    if storage_backend() == "s3":
        return  # objects are kept; lifecycle rules handle them
    folder = media_root() / safe_part(user_id)
    for path in folder.glob(f"{safe_part(item_id)}_*"):
        path.unlink(missing_ok=True)
