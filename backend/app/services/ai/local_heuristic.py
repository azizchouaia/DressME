"""Placeholder analyzer that runs locally with no ML model.

It only estimates the dominant garment color from pixels; category and other
attributes are left empty for the user to fill in. Replace with a PyTorch /
open-source vision model by implementing `ClothingAnalyzer`.
"""

import io
from collections import Counter

from PIL import Image

from app.services.ai.base import ClothingAnalysis, ClothingAnalyzer

NAMED_COLORS: dict[str, tuple[int, int, int]] = {
    "black": (25, 25, 28),
    "white": (240, 240, 236),
    "gray": (128, 128, 128),
    "navy": (30, 40, 80),
    "blue": (60, 100, 170),
    "light blue": (150, 185, 220),
    "red": (180, 40, 45),
    "burgundy": (110, 30, 45),
    "pink": (230, 160, 180),
    "orange": (225, 120, 40),
    "yellow": (230, 200, 60),
    "beige": (210, 190, 155),
    "brown": (110, 75, 50),
    "green": (60, 130, 70),
    "olive": (105, 105, 65),
    "purple": (110, 70, 140),
}


def _nearest_color(rgb: tuple[int, int, int]) -> str:
    return min(
        NAMED_COLORS,
        key=lambda name: sum((a - b) ** 2 for a, b in zip(rgb, NAMED_COLORS[name], strict=True)),
    )


class LocalHeuristicAnalyzer(ClothingAnalyzer):
    name = "local-heuristic"

    async def analyze(self, image: bytes) -> ClothingAnalysis:
        img = Image.open(io.BytesIO(image)).convert("RGB")
        img.thumbnail((96, 96))
        w, h = img.size
        pixels = list(img.getdata())

        border = [img.getpixel((x, y)) for x in range(w) for y in (0, h - 1)]
        border += [img.getpixel((x, y)) for y in range(h) for x in (0, w - 1)]
        bg = _nearest_color(Counter(_quantize(p) for p in border).most_common(1)[0][0])

        names = Counter(_nearest_color(_quantize(p)) for p in pixels)
        garment_colors = [(n, c) for n, c in names.most_common() if n != bg] or names.most_common()
        primary = garment_colors[0][0]
        secondary = garment_colors[1][0] if len(garment_colors) > 1 else None
        share = garment_colors[0][1] / max(1, sum(c for _, c in garment_colors))
        if secondary and garment_colors[1][1] / max(1, garment_colors[0][1]) < 0.35:
            secondary = None

        return ClothingAnalysis(
            primary_color=primary,
            secondary_color=secondary,
            pattern="plain" if secondary is None else None,
            confidence=round(min(0.9, 0.4 + share / 2), 2),
            analyzer=self.name,
        )


def _quantize(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    r, g, b = rgb
    return (r // 16 * 16 + 8, g // 16 * 16 + 8, b // 16 * 16 + 8)
