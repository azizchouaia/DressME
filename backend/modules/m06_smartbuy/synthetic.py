"""Synthetic data for BO5 (wardrobes, candidates + labels, fictional shops, size charts).

Run from backend/:   python -m modules.m06_smartbuy.synthetic
Writes to ml/data/bo5/synthetic/ + partners.json + size_charts.json.

Everything here is FAKE but structured like the real data:
- embeddings are built from attributes (category, type, colour, formality) so that
  similarity behaves like a real image model (same type+colour ~0.95+, same type other colour ~0.8);
- labels come from simple "stylist rules" + 8 % noise (humans disagree), NOT from the agent,
  so the accuracy you measure is a sanity check, not a final result.
Shops and brands are fictional: replace with real data before the demo.
"""

import csv
import json
import math
import random
from pathlib import Path

# ---------------------------------------------------------------- catalogue
TYPES = {  # subcategory: (category, formality 0..1, typical price TND)
    "shirt": ("top", 0.7, 70), "t-shirt": ("top", 0.2, 35), "sweater": ("top", 0.4, 90), "blouse": ("top", 0.6, 75),
    "jeans": ("bottom", 0.3, 95), "chinos": ("bottom", 0.6, 85), "trousers": ("bottom", 0.8, 110), "skirt": ("bottom", 0.5, 70),
    "sneakers": ("shoes", 0.2, 140), "loafers": ("shoes", 0.7, 160), "boots": ("shoes", 0.5, 190), "sandals": ("shoes", 0.2, 60),
    "jacket": ("outerwear", 0.4, 170), "coat": ("outerwear", 0.7, 260), "blazer": ("outerwear", 0.9, 220),
    "dress": ("dress", 0.6, 130), "jebba": ("traditional", 0.8, 350),
}
CATS = ["top", "bottom", "shoes", "outerwear", "dress", "traditional"]
SUBS = list(TYPES)
COLOURS = {  # name: (hex, neutral?)
    "white": ("#F2F2EE", True), "black": ("#1D1D1F", True), "grey": ("#8E8E8E", True), "navy": ("#1F2A44", True),
    "beige": ("#D8C3A0", True), "brown": ("#6B4A2E", True), "camel": ("#C19A6B", True), "blue": ("#3B6EA8", True),
    "olive": ("#6B7A3A", False), "red": ("#B0303A", False), "pink": ("#E79AB4", False), "green": ("#2F6B4F", False),
    "burgundy": ("#6E1F2F", False), "mustard": ("#C9A227", False),
}
TYPE_COLOURS = {  # realistic colours per type
    "shirt": ["white", "navy", "blue", "pink", "olive", "black"], "t-shirt": ["white", "black", "grey", "navy", "olive", "red", "mustard"],
    "sweater": ["grey", "navy", "camel", "burgundy", "green", "beige"], "blouse": ["white", "pink", "red", "black", "beige"],
    "jeans": ["blue", "black", "grey", "white"], "chinos": ["beige", "navy", "olive", "camel"], "trousers": ["black", "grey", "navy", "beige"],
    "skirt": ["black", "beige", "burgundy", "navy", "pink"], "sneakers": ["white", "black", "grey"], "loafers": ["brown", "black", "burgundy"],
    "boots": ["brown", "black", "camel"], "sandals": ["brown", "beige", "black"], "jacket": ["olive", "black", "navy", "blue", "camel"],
    "coat": ["camel", "black", "grey", "navy"], "blazer": ["navy", "black", "grey", "beige"], "dress": ["black", "red", "navy", "green", "pink", "beige"],
    "jebba": ["white", "beige", "grey"],
}
SLOTS = {  # what a piece combines with to make one outfit
    "top": ["bottom", "shoes"], "bottom": ["top", "shoes"], "shoes": ["top", "bottom"],
    "outerwear": ["top", "bottom"], "dress": ["shoes"], "traditional": ["shoes"],
}
GAP_POOL = ["white shirt", "any jacket", "black loafers", "navy blazer", "beige chinos", "white sneakers", "any coat", "black trousers"]


def _hex_rgb(h):
    return [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]


def embed(subcategory: str, colour: str, rng: random.Random | None = None) -> list[float]:
    """Attribute embedding that mimics an image model (FashionCLIP stand-in), 32-d."""
    cat, formality, _ = TYPES[subcategory]
    v = [0.0] * len(CATS)
    v[CATS.index(cat)] = 1.0
    s = [0.0] * len(SUBS)
    s[SUBS.index(subcategory)] = 0.9
    rgb = [x * 0.7 for x in _hex_rgb(COLOURS[colour][0])]
    vec = v + s + rgb + [formality * 0.4] + [1.0 if COLOURS[colour][1] else 0.0]
    if rng:
        vec = [x + rng.gauss(0, 0.04) for x in vec]
    return [round(x, 4) for x in vec]


def compatible(a_colour: str, b_colour: str) -> bool:
    na, nb = COLOURS[a_colour][1], COLOURS[b_colour][1]
    return na or nb  # two strong colours together = no (simple rule)


def combos(cand: dict, items: list[dict]) -> list[list[str]]:
    """Outfits the candidate creates with the wardrobe (stand-in for M2)."""
    slots = SLOTS[cand["category"]]
    pools = [[it for it in items if it["category"] == s and compatible(cand["colour"], it["colour"])
              and abs(TYPES[it["subcategory"]][1] - TYPES[cand["subcategory"]][1]) <= 0.5] for s in slots]
    if len(pools) == 1:
        return [[a["id"]] for a in pools[0]]
    return [[a["id"], b["id"]] for a in pools[0] for b in pools[1] if compatible(a["colour"], b["colour"])][:40]


BASE_WEARS = {"t-shirt": 40, "jeans": 50, "sneakers": 90, "shirt": 25, "sweater": 25, "blouse": 20, "chinos": 30,
              "trousers": 25, "skirt": 15, "loafers": 30, "boots": 35, "sandals": 25, "jacket": 35, "coat": 40,
              "blazer": 15, "dress": 8, "jebba": 4}


def wear_count(sub: str, col: str, rng: random.Random) -> int:
    """Wears per year: depends on type, neutral colours are worn more, 10 % never worn."""
    if rng.random() < 0.1:
        return 0
    k = 1.3 if COLOURS[col][1] else 0.6
    return max(0, round(BASE_WEARS[sub] * k * rng.lognormvariate(0, 0.35)))


def label(text: str) -> str:
    return text[:1].upper() + text[1:]


# ---------------------------------------------------------------- generators
def make_wardrobe(uid: str, rng: random.Random, n: int) -> dict:
    items, k = [], 0
    base = ["shirt", "t-shirt", "t-shirt", "jeans", "chinos", "sneakers", "jacket"]
    pool = base + rng.sample(SUBS, len(SUBS))
    while len(items) < n:
        sub = pool[k % len(pool)] if k < len(pool) else rng.choice(SUBS)
        col = rng.choice(TYPE_COLOURS[sub])
        k += 1
        if any(i["subcategory"] == sub and i["colour"] == col for i in items) and rng.random() < 0.7:
            continue
        items.append({"id": f"{uid}_i{len(items) + 1:02d}", "label": label(f"{col} {sub}"), "category": TYPES[sub][0],
                      "subcategory": sub, "colour": col, "embedding": embed(sub, col, rng),
                      "wear_count": wear_count(sub, col, rng)})
    owned = {f"{i['colour']} {i['subcategory']}" for i in items}
    owned_types = {i["subcategory"] for i in items}
    gaps = [g for g in GAP_POOL if g not in owned and not (g.startswith("any ") and g[4:] in owned_types)]
    return {"user_id": uid, "gaps": rng.sample(gaps, min(3, len(gaps))), "items": items}


def stylist_label(c: dict, w: dict, rng: random.Random) -> str:
    """Independent 'human stylist' rules + noise. Not the agent's score."""
    items = w["items"]
    if any(i["subcategory"] == c["subcategory"] and i["colour"] == c["colour"] for i in items):
        lab = "skip"
    else:
        n = len(combos(c, items))
        same = sum(i["subcategory"] == c["subcategory"] for i in items)
        fair = c["price_tnd"] <= TYPES[c["subcategory"]][2] * 1.3
        gap = any((g.split()[0] in (c["colour"], "any")) and g.split()[1] == c["subcategory"] for g in w["gaps"])
        if n < 2:
            lab = "skip"
        elif gap and fair:
            lab = "buy"
        elif n >= 6 and same < 3 and fair:
            lab = "buy"
        else:
            lab = "think"
    if rng.random() < 0.08:  # human disagreement
        lab = rng.choice([x for x in ("buy", "think", "skip") if x != lab])
    return lab


def make_candidates(wardrobes: list[dict], rng: random.Random, n: int) -> list[dict]:
    out = []
    for k in range(n):
        w = rng.choice(wardrobes)
        if rng.random() < 0.25:  # near-duplicate of an owned piece
            it = rng.choice(w["items"])
            sub, col = it["subcategory"], it["colour"]
        else:
            sub = rng.choice(SUBS)
            col = rng.choice(TYPE_COLOURS[sub])
        price = round(TYPES[sub][2] * rng.uniform(0.6, 1.6))
        c = {"id": f"cand_{k + 1:03d}", "user_id": w["user_id"], "label": label(f"{col} {sub}"), "category": TYPES[sub][0],
             "subcategory": sub, "colour": col, "price_tnd": price, "embedding": embed(sub, col, rng)}
        c["expected"] = stylist_label(c, w, rng)
        out.append(c)
    return out


SHOPS = [  # FICTIONAL shops — replace with real Tunisian partners
    ("Medina Atelier", "Tunis"), ("Carthage Denim Co.", "La Marsa"), ("Sahel Threads", "Sousse"),
    ("Sfax Tailors", "Sfax"), ("Cap Bon Linen", "Nabeul"),
]


def make_partners(rng: random.Random) -> dict:
    shops = []
    for name, city in SHOPS:
        slug = name.lower().replace(" ", "-").replace(".", "")
        subs = rng.sample(SUBS, 10)
        items = []
        for j, sub in enumerate(subs):
            for col in rng.sample(TYPE_COLOURS[sub], min(2, len(TYPE_COLOURS[sub]))):
                items.append({"name": label(f"{col} {sub}"), "subcategory": sub, "colour": col,
                              "price_tnd": round(TYPES[sub][2] * rng.uniform(0.7, 1.3)),
                              "url": f"https://{slug}.example/p/{j}-{col}"})
        shops.append({"name": name, "city": city, "url": f"https://{slug}.example",
                      "promo_code": f"DRESSME{rng.choice([5, 10, 15])}", "items": items})
    return {"_note": "FICTIONAL shops generated by synthetic.py - replace with real Tunisian partners", "shops": shops}


def make_size_charts() -> dict:
    """Standard EU ranges, shifted per fictional brand (slim / regular / large fit)."""
    def tops(shift):
        return [{"size": s, "chest_cm": [lo + shift, lo + 6 + shift]} for s, lo in
                (("XS", 82), ("S", 89), ("M", 96), ("L", 103), ("XL", 110), ("XXL", 117))]

    def bottoms(shift):
        return [{"size": str(s), "waist_cm": [lo + shift, lo + 4 + shift]} for s, lo in
                ((36, 68), (38, 73), (40, 78), (42, 83), (44, 88), (46, 93))]
    fits = {"Medina Atelier": 0, "Carthage Denim Co.": -2, "Sahel Threads": 2, "Sfax Tailors": 0, "Cap Bon Linen": 3}
    charts = {b: {"fit": {-2: "slim", 0: "regular", 2: "relaxed", 3: "loose"}[s], "top": tops(s), "bottom": bottoms(s)} for b, s in fits.items()}
    return {"_note": "FICTIONAL brands, standard EU ranges - replace with real charts", **charts}


def main(out: Path | None = None, seed: int = 42):
    here = Path(__file__).resolve().parent
    out = out or (here.parent.parent.parent / "ml" / "data" / "bo5")
    syn = out / "synthetic"
    syn.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    users = [("usr_amine", 28), ("usr_sarra", 34), ("usr_lina", 40), ("usr_kenza", 36), ("usr_karim", 24)]
    wardrobes = [make_wardrobe(u, rng, n) for u, n in users]
    cands = make_candidates(wardrobes, rng, 120)
    (syn / "wardrobes.json").write_text(json.dumps(wardrobes, indent=1), encoding="utf-8")
    (syn / "candidates.json").write_text(json.dumps(cands, indent=1), encoding="utf-8")
    with (syn / "labels.csv").open("w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(["image", "user_id", "price_tnd", "label"])
        for c in cands:
            wr.writerow([c["id"], c["user_id"], c["price_tnd"], c["expected"]])
    (out / "partners.json").write_text(json.dumps(make_partners(rng), indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "size_charts.json").write_text(json.dumps(make_size_charts(), indent=1), encoding="utf-8")
    dist = {k: sum(c["expected"] == k for c in cands) for k in ("buy", "think", "skip")}
    print(f"wrote {len(wardrobes)} wardrobes ({sum(len(w['items']) for w in wardrobes)} items), "
          f"{len(cands)} candidates {dist}, {len(SHOPS)} shops, size charts -> {out}")


if __name__ == "__main__":
    main()
