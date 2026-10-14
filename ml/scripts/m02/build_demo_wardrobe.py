"""Build the M2 demo wardrobes from the Kaggle "Clothing dataset (full)" (agrigorev). No training.

Stand-in for M1 until its real /m01/items exists. Every photo goes through pretrained FashionCLIP
(patrickjohncyh/fashion-clip):
  1. image embedding (512)
  2. zero-shot tags: colour, pattern, menswear / womenswear (category comes from the dataset label)
  3. description "black striped t-shirt" -> text embedding (512)
  4. item vector = [image | text] (1024), the input format of the pretrained OutfitTransformer
Then the zero-shot attribute prompts (warmth, formality, mood) are embedded and their raw scores are
standardised on these photos, and two demo users are sampled (demo_f / demo_m, ~70 pieces each).

Input : ml/data/clothing_dataset/{images.csv, images_compressed/}
Output: ml/models/m02/{wardrobe_items.json, wardrobe_emb.npy, prompts.npz, demo_wardrobes.json}

    python ml/scripts/m02/build_demo_wardrobe.py
"""

from __future__ import annotations

import csv
import json
import random
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend"))
from modules.m02_recommendation.engine import encoder  # noqa: E402
from modules.m02_recommendation.engine.attributes import build_prompt_file  # noqa: E402

DATA = ROOT / "ml/data/clothing_dataset"
OUT = ROOT / "ml/models/m02"

# Kaggle label -> (DressMe GarmentCategory, subcategory)
LABELS = {
    "T-Shirt": ("top", "t-shirt"),
    "Longsleeve": ("top", "long-sleeve top"),
    "Shirt": ("top", "shirt"),
    "Polo": ("top", "polo shirt"),
    "Top": ("top", "top"),
    "Blouse": ("top", "blouse"),
    "Hoodie": ("top", "hoodie"),
    "Pants": ("bottom", "pants"),
    "Shorts": ("bottom", "shorts"),
    "Skirt": ("bottom", "skirt"),
    "Dress": ("dress", "dress"),
    "Outwear": ("outerwear", "jacket"),
    "Blazer": ("outerwear", "blazer"),
    "Shoes": ("shoes", "shoes"),
    "Hat": ("accessory", "hat"),
}
COLOURS = {
    "black": "#1f1f22",
    "white": "#f4f2ee",
    "grey": "#9a9c9e",
    "beige": "#d8c8aa",
    "brown": "#7a5236",
    "navy": "#24324f",
    "blue": "#3b6db3",
    "light blue": "#a9c4e0",
    "green": "#4f7a55",
    "olive": "#6b6b3a",
    "red": "#b3302f",
    "burgundy": "#6d1f2c",
    "pink": "#e39ab0",
    "purple": "#6d4c8f",
    "yellow": "#e0b526",
    "orange": "#e07b26",
    "khaki": "#b8a77a",
}
PATTERNS = {"solid": "", "striped": "striped", "checked": "checked", "floral": "floral", "printed": "printed"}


def zero_shot(img: np.ndarray, subs: list[str], template: str, names: list[str]) -> list[str]:
    """Category-aware zero-shot: "a photo of a navy skirt" beats "a navy piece of clothing" on busy photos."""
    out = [""] * len(img)
    for sub in sorted(set(subs)):
        idx = [k for k, s in enumerate(subs) if s == sub]
        t = encoder.embed_texts([template.format(n=n, sub=sub) for n in names])
        for k, j in zip(idx, (img[idx] @ t.T).argmax(1), strict=True):
            out[k] = names[j]
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = [
        r
        for r in csv.DictReader(open(DATA / "images.csv", encoding="utf-8"))
        if r["label"] in LABELS
        and r["kids"] == "False"
        and (DATA / "images_compressed" / f"{r['image']}.jpg").exists()
    ]
    print(f"{len(rows)} usable photos", flush=True)

    part = OUT / "wardrobe_img.partial.npy"
    embs = list(np.load(part)) if part.exists() else []
    if (OUT / "wardrobe_emb.npy").exists() and len(np.load(OUT / "wardrobe_emb.npy")) == len(rows):
        embs = list(np.load(OUT / "wardrobe_emb.npy")[:, :512])  # already embedded: only re-tag
    t0 = time.time()
    for i in range(len(embs), len(rows), 32):
        ims = [Image.open(DATA / "images_compressed" / f"{r['image']}.jpg") for r in rows[i : i + 32]]
        embs.extend(encoder.embed_images(ims))
        if (i // 32) % 10 == 0:
            np.save(part, np.stack(embs))
            print(
                f"  {len(embs)}/{len(rows)}  {(len(embs)) / (time.time() - t0 + 1e-9):.1f} img/s", flush=True
            )
    img = np.stack(embs).astype(np.float32)

    subs = [LABELS[r["label"]][1] for r in rows]
    colour = zero_shot(img, subs, "a photo of a {n} {sub}", list(COLOURS))
    pattern = zero_shot(
        img, subs, "a photo of a {n} {sub}", ["plain", "striped", "checked", "floral", "printed"]
    )
    pattern = ["solid" if p == "plain" else p for p in pattern]
    gender = zero_shot(img, subs, "a photo of a {n} {sub}", ["women's", "men's"])
    gender = ["f" if g == "women's" else "m" for g in gender]

    items, descriptions = [], []
    for r, c, p, g in zip(rows, colour, pattern, gender, strict=True):
        cat, sub = LABELS[r["label"]]
        if sub in ("dress", "skirt", "blouse"):
            g = "f"
        descriptions.append(" ".join(x for x in (c, PATTERNS[p], sub) if x))
        items.append(
            {
                "item_id": f"k_{r['image'][:8]}",
                "image": r["image"],
                "category": cat,
                "subcategory": sub,
                "colors": [{"name": c, "hex": COLOURS[c], "share": 1.0}],
                "pattern": p,
                "gender": g,
                "description": descriptions[-1],
            }
        )
    vec = encoder.item_vectors(img, descriptions)
    json.dump(items, open(OUT / "wardrobe_items.json", "w"), indent=1)
    np.save(OUT / "wardrobe_emb.npy", vec)
    build_prompt_file(encoder.embed_texts, img)
    part.unlink(missing_ok=True)

    rng = random.Random(2026)
    quota = {"top": 26, "bottom": 14, "dress": 6, "outerwear": 8, "shoes": 10, "accessory": 3}
    demo = {}
    for user, g in (("demo_f", "f"), ("demo_m", "m")):
        ids = []
        for cat, n in quota.items():
            if g == "m" and cat == "dress":
                continue
            pool = [it["item_id"] for it in items if it["category"] == cat and it["gender"] == g]
            ids += rng.sample(pool, min(n + (6 if g == "m" and cat == "top" else 0), len(pool)))
        demo[user] = ids
    json.dump(demo, open(OUT / "demo_wardrobes.json", "w"), indent=1)
    print({u: len(v) for u, v in demo.items()}, f"done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
