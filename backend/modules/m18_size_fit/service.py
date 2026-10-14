"""M18 — Size & fit advice (rule-based on brand size charts)."""

import json
from pathlib import Path

MEASURES = {"top": "chest_cm", "outerwear": "chest_cm", "dress": "chest_cm", "bottom": "waist_cm"}


def load_charts(data_dir: Path) -> dict:
    p = data_dir / "size_charts.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def advise(charts: dict, brand: str | None, category: str, body: dict | None) -> dict | None:
    if not (brand and body) or not isinstance(charts.get(brand), dict) or category not in MEASURES:
        return None
    m = MEASURES[category]
    value = body.get(m)
    table = charts[brand].get("bottom" if category == "bottom" else "top")
    if value is None or not table:
        return None
    for row in table:
        lo, hi = row[m]
        if lo <= value <= hi:
            edge = value >= hi - 1 or value <= lo + 1
            note = f"{m.split('_')[0]} {value} cm is in {brand} size {row['size']} ({lo}-{hi})"
            return {"brand": brand, "size": row["size"], "note": note + (" - between sizes, try both" if edge else "")}
    return {"brand": brand, "size": "?", "note": f"{m.split('_')[0]} {value} cm is outside {brand}'s chart"}
