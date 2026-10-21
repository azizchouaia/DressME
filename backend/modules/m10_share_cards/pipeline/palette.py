"""Card colours chosen from the garments' own colours (colour science, no model needed).

1. Take the dominant colour of every item (from M1).
2. Mean luminance decides the background: light clothes → dark muted background, dark clothes → light tint,
   so the garments always stand out.
3. The background keeps the hue of the most saturated item, which makes the card feel "in palette".
4. Text colour is picked by WCAG contrast ratio (≥ 4.5 : 1).
"""

import colorsys
from dataclasses import dataclass

DEFAULT_HEX = "#C9C6CC"


@dataclass(frozen=True)
class Palette:
    background: str
    text: str
    muted: str
    accent: str


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def rgb_to_hex(rgb: tuple[float, float, float]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*(max(0, min(255, round(c))) for c in rgb))


def relative_luminance(h: str) -> float:
    def lin(c: float) -> float:
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = hex_to_rgb(h)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(a: str, b: str) -> float:
    la, lb = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _hls_hex(h: float, l: float, s: float) -> str:  # noqa: E741 (HLS naming)
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return rgb_to_hex((r * 255, g * 255, b * 255))


def run(item_hexes: list[str | None]) -> Palette:
    hexes = [h for h in item_hexes if h] or [DEFAULT_HEX]
    lum = sum(relative_luminance(h) for h in hexes) / len(hexes)

    # hue of the most saturated garment (a grey outfit gives a neutral, slightly warm card)
    best = max(hexes, key=lambda h: colorsys.rgb_to_hls(*(c / 255 for c in hex_to_rgb(h)))[2])
    hue, _, sat = colorsys.rgb_to_hls(*(c / 255 for c in hex_to_rgb(best)))
    if sat < 0.12:
        hue, sat = 0.08, 0.10

    if lum > 0.55:  # light clothes → deep background
        bg = _hls_hex(hue, 0.20, min(0.35, sat))
    else:  # dark / mid clothes → pale tint
        bg = _hls_hex(hue, 0.94, min(0.40, sat))

    text = "#FFFFFF" if contrast_ratio(bg, "#FFFFFF") >= contrast_ratio(bg, "#1E1B22") else "#1E1B22"
    muted = _hls_hex(hue, 0.75 if text == "#FFFFFF" else 0.40, 0.12)
    accent = _hls_hex((hue + 0.5) % 1.0, 0.45, 0.55)  # complementary hue for small highlights
    return Palette(background=bg, text=text, muted=muted, accent=accent)
