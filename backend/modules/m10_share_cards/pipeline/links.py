"""Share links with a referral code, so every new user can be traced back to the card that brought them."""

import hashlib
import secrets
from urllib.parse import quote

ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"


def base62(n: int, length: int = 7) -> str:
    out = []
    for _ in range(length):
        n, r = divmod(n, 62)
        out.append(ALPHABET[r])
    return "".join(reversed(out))


def short_code(user_id: str, source_id: str | None = None, nonce: str | None = None) -> str:
    """7-character code (62^7 ≈ 3.5e12 combinations). Nonce avoids collisions for repeated shares."""
    nonce = nonce or secrets.token_hex(4)
    digest = hashlib.sha256(f"{user_id}|{source_id}|{nonce}".encode()).digest()
    return base62(int.from_bytes(digest[:8], "big"))


def share_url(base_url: str, code: str) -> str:
    return f"{base_url.rstrip('/')}/s/{code}"


CHANNELS = ("whatsapp", "instagram", "facebook", "x", "copy", "qr")


def channel_links(url: str, caption: str) -> dict[str, str]:
    """One link per channel. `?ch=` tags the open, so the KPIs show which channel brings users.
    Instagram has no web share intent: the app saves the PNG and puts the tagged link in the story sticker."""
    tag = {ch: f"{url}?ch={ch}" for ch in CHANNELS}
    text = caption.strip()
    return {
        "whatsapp": "https://wa.me/?text=" + quote(text + " " + tag["whatsapp"]),
        "facebook": "https://www.facebook.com/sharer/sharer.php?u=" + quote(tag["facebook"], safe=""),
        "x": "https://twitter.com/intent/tweet?text=" + quote(text) + "&url=" + quote(tag["x"], safe=""),
        "instagram": tag["instagram"],
        "copy": tag["copy"],
        "qr": tag["qr"],
    }
