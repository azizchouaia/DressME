"""Download one photo per product into ml/data/shops/images/ as a resized JPEG named after the product URL."""

import hashlib
import io
import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageOps

from .client import Http

MAX_SIDE = 800  # px; plenty for FashionCLIP (224) and for the app thumbnails

log = logging.getLogger("localcatalogue.scraper")


def image_name(product_url: str) -> str:
    """Stable file name: product_id is renumbered on every run, the product URL is not."""
    return hashlib.sha1(product_url.encode()).hexdigest()[:16] + ".jpg"


def download_images(rows: list[dict], http: Http, folder: Path) -> None:
    """Set row["image_path"] (relative to the CSV folder) for each row, "" when the photo cannot be fetched.

    Photos already on disk are reused, so a refresh only downloads new products. Photos of products
    that left the catalogue are deleted.
    """
    folder.mkdir(parents=True, exist_ok=True)
    by_host: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_host[urlsplit(row["image_url"]).netloc].append(row)

    def work(host_rows: list[dict]) -> None:
        for row in host_rows:
            row["image_path"] = _fetch(row, http, folder)

    # One thread per host: hosts are fetched in parallel, each host politely in sequence.
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, by_host.values()))

    keep = {image_name(row["product_url"]) for row in rows}
    for path in folder.glob("*.jpg"):
        if path.name not in keep:
            path.unlink()


def _fetch(row: dict, http: Http, folder: Path) -> str:
    target = folder / image_name(row["product_url"])
    relative = f"{folder.name}/{target.name}"
    if target.exists() and target.stat().st_size > 0:
        return relative
    if not row["image_url"]:
        return ""
    try:
        img = Image.open(io.BytesIO(http.get(row["image_url"]).content))
        img = ImageOps.exif_transpose(img)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            background = Image.new("RGB", img.size, "white")  # transparent cut-outs on white
            background.paste(img, mask=img.getchannel("A"))
            img = background
        img = img.convert("RGB")
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        img.save(target, "JPEG", quality=85, optimize=True)
        return relative
    except Exception as exc:  # broken link, HTML instead of an image, unsupported format...
        log.warning("photo failed for %s: %s", row["product_url"], f"{type(exc).__name__}: {exc}"[:150])
        return ""
