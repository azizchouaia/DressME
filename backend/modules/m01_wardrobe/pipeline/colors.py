"""Dominant colours: K-means (k=3) in CIE-LAB on the masked pixels only, named by nearest palette entry."""

import numpy as np

from shared.schemas import Color

_SRGB_TO_XYZ = np.array([
    [0.4124564, 0.3575761, 0.1804375],
    [0.2126729, 0.7151522, 0.0721750],
    [0.0193339, 0.1191920, 0.9503041],
])
_D65 = np.array([0.95047, 1.0, 1.08883])
_EPS = (6 / 29) ** 3


def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """(..., 3) sRGB in [0, 255] -> (..., 3) CIE-LAB (D65)."""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    lin = np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    xyz = (lin @ _SRGB_TO_XYZ.T) / _D65
    f = np.where(xyz > _EPS, np.cbrt(xyz), xyz / (3 * (6 / 29) ** 2) + 4 / 29)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], -1)


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb) -> str:
    r, g, b = (int(round(float(v))) for v in rgb)
    return f"#{r:02X}{g:02X}{b:02X}"


def name_color(lab: np.ndarray, palette: dict[str, str]) -> str:
    names = list(palette)
    ref = srgb_to_lab(np.array([hex_to_rgb(palette[n]) for n in names]))
    return names[int(np.argmin(np.linalg.norm(ref - lab, axis=1)))]


def dominant_colors(
    rgba,
    palette: dict[str, str],
    k: int = 3,
    max_pixels: int = 20_000,
    min_share: float = 0.03,
    seed: int = 0,
) -> list[Color]:
    """`rgba`: PIL image or (H, W, 4) array; pixels with alpha <= 127 are ignored (background)."""
    from sklearn.cluster import KMeans

    arr = np.asarray(rgba.convert("RGBA") if hasattr(rgba, "convert") else rgba)
    px = arr[..., :3][arr[..., 3] > 127]
    if len(px) == 0:
        return []
    if len(px) > max_pixels:
        px = px[np.random.default_rng(seed).choice(len(px), max_pixels, replace=False)]

    lab = srgb_to_lab(px)
    k = min(k, len(np.unique(px, axis=0)))
    km = KMeans(n_clusters=k, n_init=4, random_state=seed).fit(lab)

    merged: dict[str, tuple[float, np.ndarray, float]] = {}    # name -> (share, rgb, biggest cluster share)
    for c in range(k):
        sel = km.labels_ == c
        share = float(sel.mean())
        name = name_color(km.cluster_centers_[c], palette)
        rgb = px[sel].mean(axis=0)
        if name in merged:
            total, best_rgb, best_share = merged[name]
            merged[name] = (total + share, rgb if share > best_share else best_rgb, max(share, best_share))
        else:
            merged[name] = (share, rgb, share)

    colors = [
        Color(name=name, hex=rgb_to_hex(rgb), share=round(min(share, 1.0), 3))
        for name, (share, rgb, _) in merged.items()
        if share >= min_share
    ]
    return sorted(colors, key=lambda c: c.share, reverse=True)
