"""Decode the `image` field of a request (base64, data URL or http(s) URL) into a PIL image."""

import base64
import binascii
import io
import ipaddress
import re
import socket
from urllib.parse import urlparse

import httpx

from ..contract import InvalidImageError

MAX_BYTES = 12 * 1024 * 1024
MAX_SIDE = 1024
_DATA_URL = re.compile(r"^data:image/[\w.+-]+;base64,", re.IGNORECASE)


def _check_public_host(url: str) -> None:
    """Basic SSRF guard: refuse URLs that resolve to private / loopback addresses."""
    host = urlparse(url).hostname
    if not host:
        raise InvalidImageError("invalid image URL")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise InvalidImageError(f"cannot resolve {host}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise InvalidImageError("image URL must point to a public host")


def _download(url: str) -> bytes:
    _check_public_host(url)
    chunks, size = [], 0
    try:
        with httpx.stream("GET", url, timeout=10, follow_redirects=False) as r:
            r.raise_for_status()
            for chunk in r.iter_bytes():
                size += len(chunk)
                if size > MAX_BYTES:
                    raise InvalidImageError("image too large (max 12 MB)")
                chunks.append(chunk)
    except httpx.HTTPError as e:
        raise InvalidImageError(f"cannot download image: {e}") from e
    return b"".join(chunks)


def read_image_bytes(image: str) -> bytes:
    s = image.strip()
    if s.startswith(("http://", "https://")):
        return _download(s)
    if m := _DATA_URL.match(s):
        s = s[m.end():]
    try:
        data = base64.b64decode("".join(s.split()), validate=True)
    except (binascii.Error, ValueError) as e:
        raise InvalidImageError("image is neither an http(s) URL nor valid base64") from e
    if not data:
        raise InvalidImageError("empty image")
    if len(data) > MAX_BYTES:
        raise InvalidImageError("image too large (max 12 MB)")
    return data


def open_image(data: bytes):
    """bytes -> PIL image, EXIF-rotated and resized to at most MAX_SIDE px."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as e:
        raise InvalidImageError("unsupported or corrupted image") from e
    img = ImageOps.exif_transpose(img)
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    return img


def encode(img, fmt: str = "PNG") -> bytes:
    buf = io.BytesIO()
    if fmt == "JPEG":
        img = img.convert("RGB")
        img.save(buf, format="JPEG", quality=90)
    else:
        img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def has_alpha(img) -> bool:
    return img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
