"""Dev stand-in for M1 (wardrobe digitiser): turn a garment photo into a cutout + colours.

Used only by /demo so BO7 can work with real clothes before M1 is live. M1 (SAM + FashionCLIP) replaces
it; nothing else in M10/M15 changes because they only read `Garment.image_cutout` and `Garment.colors`.

Steps (shown in the demo trace):
  1. DL  · background removal with `rembg` (U²-Net) when it is installed,
     else  if/else · border-colour flood fill (works well on a plain wall / bed / floor background)
  2. if/else · crop to the garment, resize
  3. ML  · K-means on the garment pixels → dominant colours, named with the nearest reference colour
"""

import io

import numpy as np
from PIL import Image

from modules.m10_share_cards.pipeline.colors_ml import dominant_colors

MAX_SIDE = 900
NAMED = {
    "black": (30, 30, 32),
    "white": (240, 238, 232),
    "grey": (150, 150, 152),
    "beige": (220, 200, 165),
    "brown": (125, 85, 55),
    "red": (190, 35, 45),
    "pink": (230, 160, 180),
    "orange": (230, 130, 40),
    "yellow": (235, 205, 60),
    "green": (80, 140, 80),
    "blue": (60, 100, 175),
    "navy": (35, 45, 80),
    "purple": (120, 70, 140),
}


def color_name(hex_: str) -> str:
    rgb = np.array([int(hex_[i : i + 2], 16) for i in (1, 3, 5)], dtype=float)
    return min(NAMED, key=lambda n: float(np.sum((rgb - np.array(NAMED[n])) ** 2)))


_SESSION: list = []  # rembg model loaded once (176 MB)


def _remove_bg_rembg(img: Image.Image) -> Image.Image | None:
    try:
        from rembg import new_session, remove  # optional: pip install rembg (downloads U²-Net on first use)
    except Exception:  # noqa: BLE001
        return None
    try:
        if not _SESSION:
            _SESSION.append(new_session("u2net"))
        return remove(img, session=_SESSION[0]).convert("RGBA")
    except Exception:  # noqa: BLE001
        return None


def _remove_bg_flood(img: Image.Image, tol: float = 38.0) -> Image.Image:
    """Pixels close to the border colour AND connected to the border are background."""
    from scipy import ndimage

    arr = np.asarray(img.convert("RGB")).astype(float)
    h, w, _ = arr.shape
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]])
    bg = np.median(border, axis=0)
    close = np.sqrt(((arr - bg) ** 2).sum(axis=2)) < tol
    labels, _ = ndimage.label(close)
    edge_labels = np.unique(np.concatenate([labels[0], labels[-1], labels[:, 0], labels[:, -1]]))
    mask_bg = np.isin(labels, edge_labels[edge_labels > 0])
    fg = ~mask_bg
    fg = ndimage.binary_opening(fg, iterations=2)
    fg = ndimage.binary_fill_holes(fg)
    alpha = (ndimage.gaussian_filter(fg.astype(float), 1.2) * 255).astype(np.uint8)
    out = np.dstack([arr.astype(np.uint8), alpha])
    return Image.fromarray(out, "RGBA")


def run(data: bytes) -> dict:
    """Returns {png: bytes, colors: [{name, hex, share}], method: str, steps: [(method, name, detail)]}."""
    img = Image.open(io.BytesIO(data))
    img = img.convert("RGBA") if img.mode in ("RGBA", "LA", "P") else img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    steps = []

    has_alpha = img.mode == "RGBA" and np.asarray(img)[:, :, 3].min() < 250
    if has_alpha:
        cut, method = img, "already transparent"
        steps.append(("data", "Cutout", "photo already has a transparent background"))
    else:
        cut = _remove_bg_rembg(img)
        if cut is not None:
            method = "rembg"
            steps.append(("DL", "Background removal", "rembg · U²-Net segmentation network"))
        else:
            cut, method = _remove_bg_flood(img), "flood"
            steps.append(
                (
                    "if/else",
                    "Background removal",
                    "border colour + flood fill (install rembg for the DL model)",
                )
            )

    alpha_full = np.asarray(cut.split()[-1])
    fg_ratio = float((alpha_full > 40).mean())
    fallback = False
    bbox = cut.split()[-1].point(lambda a: 255 if a > 40 else 0).getbbox()
    if not bbox or (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]) < 0.03 * cut.width * cut.height:
        cut, bbox = img.convert("RGBA"), (0, 0, img.width, img.height)  # segmentation failed: keep photo
        fallback = True
        steps.append(("if/else", "Fallback", "garment not found, the whole photo is kept"))
    cut = cut.crop(bbox)
    steps.append(("if/else", "Crop", f"cropped to the garment · {cut.width}×{cut.height}px"))

    cols = dominant_colors(cut, k=3)
    colors = [{"name": color_name(h), "hex": h, "share": s} for h, s in cols if s >= 0.05] or [
        {"name": color_name(cols[0][0]), "hex": cols[0][0], "share": cols[0][1]}
    ]
    steps.append(
        (
            "ML",
            "K-means colours",
            ", ".join(f"{c['name']} {c['hex']} {round(c['share'] * 100)}%" for c in colors),
        )
    )

    buf = io.BytesIO()
    cut.save(buf, format="PNG")
    return {
        "png": buf.getvalue(),
        "colors": colors,
        "method": method,
        "steps": steps,
        "fg_ratio": round(fg_ratio, 3),  # share of the photo kept as garment (quality check)
        "fallback": fallback,
    }
