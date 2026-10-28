"""Flat-lay layout: place garments on the card the way a stylist lays clothes on a table.

Garments are grouped in rows by where they are worn on the body:
  upper  = outerwear, top, dress, traditional (jebba, kachabia, sefsari are full length)
  lower  = bottom
  feet   = shoes and accessories
Empty rows are dropped and the remaining rows share the height in proportion to their weight.
Pure function, no image code, so it is easy to test.
"""

from dataclasses import dataclass

ROW_OF = {
    "outerwear": "upper",
    "top": "upper",
    "dress": "upper",
    "traditional": "upper",
    "bottom": "lower",
    "shoes": "feet",
    "accessory": "feet",
}
ROW_ORDER = ("upper", "lower", "feet")
# Inside a row, items are ordered left → right like a real flat-lay.
ITEM_ORDER = {"outerwear": 0, "top": 1, "dress": 1, "traditional": 1, "bottom": 2, "shoes": 3, "accessory": 4}
DEFAULT_WEIGHTS = {"upper": 0.42, "lower": 0.36, "feet": 0.22}


@dataclass(frozen=True)
class Box:
    item_id: str
    x: int
    y: int
    w: int
    h: int


def run(
    items: list[dict],
    area: tuple[int, int, int, int],
    gutter: int = 24,
    weights: dict[str, float] | None = None,
) -> list[Box]:
    """items: [{"item_id", "category"}]; area: (x, y, width, height) available for garments."""
    if not items:
        return []
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    rows: dict[str, list[dict]] = {r: [] for r in ROW_ORDER}
    for it in items:
        rows[ROW_OF.get(str(it["category"]), "feet")].append(it)
    present = [r for r in ROW_ORDER if rows[r]]

    # A lone row of two upper pieces looks better when the bottom row takes more room, so weights
    # are renormalised on the rows that exist.
    total_w = sum(weights[r] for r in present)
    ax, ay, aw, ah = area
    usable_h = ah - gutter * (len(present) - 1)

    boxes: list[Box] = []
    y = ay
    for r in present:
        row_h = round(usable_h * weights[r] / total_w)
        row_items = sorted(rows[r], key=lambda it: ITEM_ORDER.get(str(it["category"]), 9))
        n = len(row_items)
        cell_w = (aw - gutter * (n - 1)) / n
        for i, it in enumerate(row_items):
            x = ax + round(i * (cell_w + gutter))
            boxes.append(Box(it["item_id"], x, y, round(cell_w), row_h))
        y += row_h + gutter
    return boxes
