"""M18 — Size & fit advice (rule-based on brand size charts).

Two ways to know the body:
1. numbers   : chest_cm / waist_cm (if the user knows them)
2. fit words : "I wear M at Brand X and it feels tight" (no tape measure needed)
   Each answer -> estimated measurement. Several answers are averaged.
The user can also say how they LIKE to wear clothes (like_fit): oversized -> we aim bigger.
"""

import json
from pathlib import Path

MEASURES = {"top": "chest_cm", "outerwear": "chest_cm", "dress": "chest_cm", "bottom": "waist_cm"}

# How the garment feels -> where the body sits vs the size range (cm from the middle of the range)
FIT_SHIFT = {"extremely_tight": 7, "tight": 3, "normal": 0, "loose": -3, "oversized": -7}
FIT_LABELS = {"extremely_tight": "extremely tight", "tight": "tight", "normal": "normal",
              "loose": "loose", "oversized": "oversized"}
# How the user LIKES to wear it -> extra room we aim for (cm)
LIKE_ROOM = {"tight": -3, "normal": 0, "loose": 3, "oversized": 7}


def load_charts(data_dir: Path) -> dict:
    p = data_dir / "size_charts.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _table(charts, brand, category):
    if not isinstance(charts.get(brand), dict) or category not in MEASURES:
        return None
    return charts[brand].get("bottom" if category == "bottom" else "top")


def estimate(charts: dict, refs: list[dict], category: str) -> dict | None:
    """Fit words -> estimated measurement. refs: [{brand, size, category, fit}]. Same part only (top vs bottom)."""
    m = MEASURES.get(category)
    if not m:
        return None
    vals, used = [], []
    for r in refs or []:
        if MEASURES.get(r.get("category")) != m or r.get("fit") not in FIT_SHIFT:
            continue
        row = next((x for x in _table(charts, r.get("brand"), r["category"]) or [] if x["size"] == str(r.get("size"))), None)
        if not row:
            continue
        lo, hi = row[m]
        vals.append((lo + hi) / 2 + FIT_SHIFT[r["fit"]])
        used.append(f"{r['brand']} {r['size']} feels {FIT_LABELS[r['fit']]}")
    if not vals:
        return None
    spread = max(vals) - min(vals)
    return {"measure": m, "value": round(sum(vals) / len(vals), 1), "from": used,
            "sure": len(vals) >= 2 and spread <= 4}


def advise(charts: dict, brand: str | None, category: str, body: dict | None) -> dict | None:
    table = _table(charts, brand, category)
    if not (table and body):
        return None
    m = MEASURES[category]
    value, how, sure = body.get(m), f"{m.split('_')[0]} {body.get(m)} cm", True
    if value is None:
        est = estimate(charts, body.get("fit_refs") or [], category)
        if not est:
            return None
        value, sure = est["value"], est["sure"]
        how = "from what you told us (" + "; ".join(est["from"]) + ")"
    like = body.get("like_fit") or "normal"
    target = value + LIKE_ROOM.get(like, 0)
    extra = f", you like it {like}" if like != "normal" else ""
    for row in table:
        lo, hi = row[m]
        if lo <= target <= hi:
            edge = target >= hi - 1 or target <= lo + 1 or not sure
            note = f"{how}{extra} -> {brand} size {row['size']}"
            return {"brand": brand, "size": row["size"], "note": note + (" - between sizes, try both" if edge else ""),
                    "estimated": body.get(m) is None}
    small = target < table[0][m][0]
    return {"brand": brand, "size": table[0]["size"] if small else table[-1]["size"],
            "note": f"{how}{extra} -> outside {brand}'s chart, closest size", "estimated": body.get(m) is None}
