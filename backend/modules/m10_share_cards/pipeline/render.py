"""Draw the card with Pillow: background, header, flat-lay of cutouts, optional stats, watermark.

If a cutout cannot be loaded (no M1 image yet, network error), a garment silhouette in the item's colour is
drawn instead, so the card always renders (mock-first rule).
"""

import base64
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .layout import Box
from .palette import Palette, hex_to_rgb

EYEBROW = {
    "outfit": "OUTFIT OF THE DAY",
    "board": "MY LOOK",
    "tryon": "TRIED ON MY AVATAR",
    "recap": "MONTHLY RECAP",
    "giveaway": "GIVE-AWAY",
    "challenge": "COMMUNITY CHALLENGE",
    "style_timeline": "MY STYLE EVOLUTION",
    "trip": "TRIP LOOKBOOK",
    "poll": "SHOULD I BUY THIS?",
}

# Silhouettes on a 40×40 grid (same shapes as the design mockups)
SILHOUETTES = {
    "top": [
        (8, 11),
        (15, 6),
        (20, 9),
        (25, 6),
        (32, 11),
        (29, 17),
        (26, 15),
        (26, 35),
        (14, 35),
        (14, 15),
        (11, 17),
    ],
    "outerwear": [
        (9, 11),
        (15, 5),
        (20, 10),
        (25, 5),
        (31, 11),
        (34, 33),
        (29, 33),
        (27, 18),
        (27, 37),
        (13, 37),
        (13, 18),
        (11, 33),
        (6, 33),
    ],
    "bottom": [(12, 4), (28, 4), (30, 37), (22.5, 37), (20, 15), (17.5, 37), (10, 37)],
    "shoes": [(5, 28), (5, 20), (13, 20), (17, 24), (22, 25.5), (30, 26), (35, 28), (35, 32), (5, 32)],
    "accessory": [(9, 15), (31, 15), (31, 34), (9, 34)],
    "dress": [(15, 5), (25, 5), (24, 13), (32, 36), (8, 36), (16, 13)],
    "traditional": [(12, 6), (17, 4), (20, 7), (23, 4), (28, 6), (31, 37), (9, 37)],
}


# Pillow's built-in font has no glyph for some typographic characters (drawn as boxes): use plain ones.
PLAIN = str.maketrans({"×": "x", "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "..."})


def _draw(img: Image.Image) -> ImageDraw.ImageDraw:
    d = ImageDraw.Draw(img)
    text, length = d.text, d.textlength
    d.text = lambda xy, t, *a, **k: text(xy, str(t).translate(PLAIN), *a, **k)
    d.textlength = lambda t, *a, **k: length(str(t).translate(PLAIN), *a, **k)
    return d


def font(size: int, path: str | None = None) -> ImageFont.FreeTypeFont:
    if path and Path(path).exists():
        return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def load_image(src: str | None, timeout: float = 4.0) -> Image.Image | None:
    """Load a cutout from a data URI, a local path, http(s) or s3://. Returns None on any failure."""
    if not src:
        return None
    try:
        if src.startswith("data:"):
            data = base64.b64decode(src.split(",", 1)[1])
        elif src.startswith(("http://", "https://")):
            import httpx

            data = httpx.get(src, timeout=timeout).raise_for_status().content
        elif src.startswith("s3://"):
            from shared.storage import s3_client

            bucket, key = src[5:].split("/", 1)
            data = s3_client().get_object(Bucket=bucket, Key=key)["Body"].read()
        elif Path(src).exists():
            data = Path(src).read_bytes()
        else:
            return None
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:  # noqa: BLE001 — a broken image must never break the card
        return None


def qr_image(url: str, size: int) -> Image.Image | None:
    """QR code of the link; None if the optional `qrcode` package is missing (the card still renders)."""
    try:
        import qrcode
    except ImportError:
        return None
    qr = qrcode.QRCode(border=0, box_size=10, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    return (
        qr.make_image(fill_color="#16233F", back_color="white")
        .get_image()
        .resize((size, size), Image.NEAREST)
    )


def _fit(img: Image.Image, w: int, h: int) -> Image.Image:
    scale = min(w / img.width, h / img.height)
    return img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)


def _silhouette(category: str, color_hex: str, w: int, h: int) -> Image.Image:
    """Garment silhouette scaled to its own bounding box, so shoes and bags fill their cell too."""
    pts = SILHOUETTES.get(category, SILHOUETTES["top"])
    top = 7 if category == "accessory" else min(y for _, y in pts)  # keep room for the bag handle
    x0, x1 = min(x for x, _ in pts), max(x for x, _ in pts)
    y1 = max(y for _, y in pts)
    k = min(w / (x1 - x0), h / (y1 - top))
    pad = 6
    img = Image.new("RGBA", (int((x1 - x0) * k) + 2 * pad, int((y1 - top) * k) + 2 * pad), (0, 0, 0, 0))
    d = _draw(img)
    poly = [((x - x0) * k + pad, (y - top) * k + pad) for x, y in pts]
    rgb = hex_to_rgb(color_hex)
    edge = tuple(max(0, c - 60) for c in rgb)
    d.polygon(poly, fill=(*rgb, 255), outline=(*edge, 255), width=max(2, int(k / 4)))
    if category == "accessory":  # bag handle
        box = ((15 - x0) * k + pad, pad, (25 - x0) * k + pad, (23 - top) * k + pad)
        d.arc(box, 180, 360, fill=(*edge, 255), width=max(3, int(k / 2)))
    return img


def _paste_with_shadow(canvas: Image.Image, piece: Image.Image, x: int, y: int) -> None:
    alpha = piece.split()[-1]
    shadow = Image.new("RGBA", piece.size, (0, 0, 0, 0))
    shadow.putalpha(alpha.point(lambda a: a * 0.28))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=max(4, piece.width // 40)))
    canvas.alpha_composite(shadow, (x + 10, y + 16))
    canvas.alpha_composite(piece, (x, y))


def _wrap(draw: ImageDraw.ImageDraw, text: str, f: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=f) <= max_w:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def run(
    *,
    kind: str,
    size: tuple[int, int],
    palette: Palette,
    boxes: list[Box],
    items: dict[str, dict],
    title: str | None,
    subtitle: str | None,
    stats: list[tuple[str, str]],
    footer: str | None,
    content_area: tuple[int, int, int, int],
    qr_url: str | None = None,
    font_path: str | None = None,
    timeout: float = 4.0,
) -> bytes:
    W, H = size
    canvas = Image.new("RGBA", size, (*hex_to_rgb(palette.background), 255))
    d = _draw(canvas)
    m = 72
    text_rgb, muted_rgb, accent_rgb = (hex_to_rgb(c) for c in (palette.text, palette.muted, palette.accent))

    # header
    y = 84
    d.text((m, y), EYEBROW.get(kind, kind.upper()), font=font(30, font_path), fill=accent_rgb)
    y += 52
    f_title = font(68 if H > 1500 else 56, font_path)
    for line in _wrap(d, title or "My look", f_title, W - 2 * m)[:2]:
        d.text((m, y), line, font=f_title, fill=text_rgb)
        y += f_title.size + 10
    if subtitle:
        d.text((m, y + 4), subtitle, font=font(34, font_path), fill=muted_rgb)

    # garments
    f_label = font(28, font_path)
    for b in boxes:
        it = items[b.item_id]
        label_h = 44 if it.get("label") else 0
        bw, bh = b.w, b.h - label_h
        cut = load_image(it.get("image"), timeout)
        piece = (
            _fit(cut, int(bw * 0.92), int(bh * 0.92))
            if cut
            else _silhouette(
                str(it["category"]), it.get("color_hex") or "#C9C6CC", int(bw * 0.6), int(bh * 0.8)
            )
        )
        px = b.x + (bw - piece.width) // 2
        py = b.y + (bh - piece.height) // 2
        _paste_with_shadow(canvas, piece, px, py)
        if it.get("label"):
            label = it["label"]
            while d.textlength(label, font=f_label) > bw and len(label) > 4:
                label = label[:-2] + "…"
            d.text(
                (b.x + (bw - d.textlength(label, font=f_label)) / 2, b.y + bh + 8),
                label,
                font=f_label,
                fill=text_rgb,
            )
        if it.get("brand"):
            f_b = font(24, font_path)
            tw = d.textlength(it["brand"], font=f_b)
            d.rounded_rectangle((b.x, b.y, b.x + tw + 28, b.y + 40), radius=20, fill=accent_rgb)
            d.text((b.x + 14, b.y + 7), it["brand"], font=f_b, fill=(255, 255, 255))

    # stats tiles (recap, timeline, challenge progress)
    if stats:
        ax, ay, aw, ah = content_area
        n = len(stats)
        cols = 2 if n > 1 else 1
        rows = (n + cols - 1) // cols
        tile_h = 180
        top = ay + ah - rows * tile_h - (rows - 1) * 20 if boxes else ay
        tw = (aw - (cols - 1) * 20) // cols
        tile_rgb = tuple((c + t) // 2 for c, t in zip(hex_to_rgb(palette.background), muted_rgb, strict=True))
        for i, (label, value) in enumerate(stats):
            cx = ax + (i % cols) * (tw + 20)
            cy = top + (i // cols) * (tile_h + 20)
            d.rounded_rectangle((cx, cy, cx + tw, cy + tile_h), radius=28, fill=(*tile_rgb, 255))
            d.text((cx + 28, cy + 26), value, font=font(64, font_path), fill=text_rgb)
            d.text((cx + 28, cy + 112), label, font=font(30, font_path), fill=text_rgb)

    # QR code of the referral link (scanned from a printed card or another screen)
    if qr_url:
        q = qr_image(qr_url, 168)
        if q is not None:
            pad = 14
            x0, y0 = W - m - q.width - 2 * pad, H - 150 - q.height - 2 * pad
            box = (x0, y0, x0 + q.width + 2 * pad, y0 + q.height + 2 * pad)
            d.rounded_rectangle(box, radius=22, fill=(255, 255, 255))
            canvas.alpha_composite(q.convert("RGBA"), (x0 + pad, y0 + pad))
            hint = "Scan to see this look on DressMe"
            f_h = font(30, font_path)
            d.text((m, y0 + (q.height + 2 * pad) // 2 - 18), hint, font=f_h, fill=text_rgb)

    # watermark / referral footer
    if footer:
        f_f = font(30, font_path)
        d.text((m, H - 96), "Made with DressMe", font=f_f, fill=text_rgb)
        d.text((W - m - d.textlength(footer, font=f_f), H - 96), footer, font=f_f, fill=muted_rgb)

    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, format="PNG", optimize=True)
    return buf.getvalue()
