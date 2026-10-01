import io
from dataclasses import dataclass
from uuid import UUID, uuid4

from PIL import Image, ImageOps, UnidentifiedImageError

from app.services.storage import StorageService

MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_IMAGE_EDGE = 1600
THUMBNAIL_EDGE = 480


class InvalidImageError(ValueError):
    pass


@dataclass
class StoredImage:
    image_key: str
    image_url: str
    thumbnail_key: str
    thumbnail_url: str


def store_clothing_image(storage: StorageService, user_id: UUID, data: bytes) -> StoredImage:
    """Normalize orientation, downscale, and store the image plus a thumbnail as JPEG."""
    if len(data) > MAX_UPLOAD_BYTES:
        raise InvalidImageError("Image is larger than 12 MB.")
    try:
        img = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("File is not a supported image.") from exc
    img = img.convert("RGB")

    stem = uuid4().hex
    full = img.copy()
    full.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE))
    thumb = img.copy()
    thumb.thumbnail((THUMBNAIL_EDGE, THUMBNAIL_EDGE))

    image_key = f"uploads/{user_id}/{stem}.jpg"
    thumbnail_key = f"thumbnails/{user_id}/{stem}.jpg"
    return StoredImage(
        image_key=image_key,
        image_url=storage.save(image_key, _jpeg(full, 88), "image/jpeg"),
        thumbnail_key=thumbnail_key,
        thumbnail_url=storage.save(thumbnail_key, _jpeg(thumb, 80), "image/jpeg"),
    )


def _jpeg(img: Image.Image, quality: int) -> bytes:
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=quality, optimize=True)
    return buffer.getvalue()
