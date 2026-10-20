"""BO7 · import a public clothing dataset into the demo wardrobe (real photos + descriptions).

Two sources:
  clothing  · "Clothing dataset" by Alexey Grigorev (GitHub, 5 403 real photos, 20 classes, free for any use)
              https://github.com/alexeygrigorev/clothing-dataset
  products  · "Fashion Product Images (Small)" (Hugging Face mirror of the Kaggle dataset, 44 k product photos
              with a description: productDisplayName, articleType, baseColour, season, usage, gender)
              https://huggingface.co/datasets/ashraq/fashion-product-images-small

Each image goes through the same pipeline as a user photo (backend/bo/bo7_sharing/demo/cutout.py):
background removal (rembg if installed, else flood fill) → crop → K-means colours (ML) → description.
Results go to backend/bo/bo7_sharing/demo_wardrobe/ (<item_id>.png + added.json), used by M15 and M10.

Usage (from the repo root, with the backend venv active):
    python ml/scripts/import_clothing_dataset.py --source clothing --per-class 6
    python ml/scripts/import_clothing_dataset.py --source products --per-class 6
    python ml/scripts/import_clothing_dataset.py --clear          # remove imported items
Options: --hide-mock hides the coloured demo items that have no photo (keeps traditional + local-brand ones).
"""

import argparse
import csv
import io
import json
import random
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
PHOTOS = ROOT / "backend" / "bo" / "bo7_sharing" / "demo_wardrobe"  # = modules.m15_challenges.wardrobe.PHOTOS

GH = "https://raw.githubusercontent.com/alexeygrigorev/clothing-dataset/master"
HF_ROWS = "https://datasets-server.huggingface.co/rows"
HF_DATASET = "ashraq/fashion-product-images-small"

# dataset label → (DressMe category, readable name)
CLOTHING = {
    "T-Shirt": ("top", "t-shirt"),
    "Longsleeve": ("top", "long-sleeve top"),
    "Shirt": ("top", "shirt"),
    "Polo": ("top", "polo"),
    "Hoodie": ("top", "hoodie"),
    "Blouse": ("top", "blouse"),
    "Top": ("top", "top"),
    "Pants": ("bottom", "trousers"),
    "Shorts": ("bottom", "shorts"),
    "Skirt": ("bottom", "skirt"),
    "Shoes": ("shoes", "shoes"),
    "Dress": ("dress", "dress"),
    "Outwear": ("outerwear", "jacket"),
    "Blazer": ("outerwear", "blazer"),
    "Hat": ("accessory", "hat"),
}
# Fashion Product Images: articleType → category (only the useful ones)
PRODUCTS = {
    **{t: "top" for t in ["Tshirts", "Shirts", "Tops", "Sweatshirts", "Sweaters", "Kurtas", "Tunics"]},
    **{t: "bottom" for t in ["Jeans", "Trousers", "Shorts", "Skirts", "Track Pants", "Capris", "Leggings"]},
    **{
        t: "shoes"
        for t in ["Casual Shoes", "Sports Shoes", "Formal Shoes", "Sandals", "Heels", "Flats", "Flip Flops"]
    },
    **{t: "outerwear" for t in ["Jackets", "Blazers", "Rain Jacket"]},
    **{t: "dress" for t in ["Dresses", "Jumpsuit"]},
    **{
        t: "accessory" for t in ["Handbags", "Caps", "Belts", "Watches", "Scarves", "Sunglasses", "Backpacks"]
    },
}
# how many items of each DressMe category we aim for, relative to --per-class
CATEGORY_WEIGHT = {"top": 3, "bottom": 2, "shoes": 2, "outerwear": 1, "dress": 1, "accessory": 1}


def load_added() -> list[dict]:
    f = PHOTOS / "added.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def save_added(rows: list[dict]) -> None:
    PHOTOS.mkdir(parents=True, exist_ok=True)
    (PHOTOS / "added.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")


def good_cutout(res: dict) -> bool:
    return not res["fallback"] and 0.12 <= res["fg_ratio"] <= 0.9


def describe(colors: list[dict], name: str) -> str:
    main = colors[0]["name"]
    second = colors[1]["name"] if len(colors) > 1 and colors[1]["share"] >= 0.2 else None
    return f"{main} {name}" if not second or second == main else f"{main} and {second} {name}"


def candidates_clothing(rng: random.Random, per_class: int):
    rows = list(csv.DictReader(io.StringIO(httpx.get(f"{GH}/images.csv", timeout=30).text)))
    by_label: dict[str, list[dict]] = {}
    for r in rows:
        if r["kids"] == "False" and r["label"] in CLOTHING:
            by_label.setdefault(r["label"], []).append(r)
    for label, items in by_label.items():
        cat, name = CLOTHING[label]
        rng.shuffle(items)
        quota = max(1, per_class * CATEGORY_WEIGHT[cat] // sum(1 for v in CLOTHING.values() if v[0] == cat))
        for r in items[: quota * 4]:  # extra candidates: some photos are rejected by the quality check
            yield {
                "key": label,
                "quota": quota,
                "url": f"{GH}/images/{r['image']}.jpg",
                "id": r["image"][:8],
                "category": cat,
                "name": name,
                "meta": {"dataset_label": label},
                "source": "clothing-dataset (A. Grigorev, CC0)",
            }


def candidates_products(rng: random.Random, per_class: int):
    offset = rng.randrange(0, 40000)
    seen = 0
    while seen < 3000:
        r = httpx.get(
            HF_ROWS,
            params={
                "dataset": HF_DATASET,
                "config": "default",
                "split": "train",
                "offset": offset,
                "length": 100,
            },
            timeout=60,
        )
        r.raise_for_status()
        rows = r.json()["rows"]
        if not rows:
            break
        for row in rows:
            x = row["row"]
            cat = PRODUCTS.get(x.get("articleType"))
            if not cat:
                continue
            img = x["image"]["src"] if isinstance(x.get("image"), dict) else x.get("image")
            yield {
                "key": cat,
                "quota": per_class * CATEGORY_WEIGHT[cat],
                "url": img,
                "id": str(x.get("id")),
                "category": cat,
                "name": (x.get("articleType") or cat).lower().rstrip("s"),
                "description": x.get("productDisplayName"),
                "meta": {
                    k: x.get(k)
                    for k in ["gender", "articleType", "baseColour", "season", "usage", "productDisplayName"]
                },
                "source": "Fashion Product Images (Kaggle / Hugging Face)",
            }
        offset += 100
        seen += 100


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["clothing", "products"], default="clothing")
    ap.add_argument("--per-class", type=int, default=6)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--hide-mock", action="store_true")
    ap.add_argument("--clear", action="store_true")
    a = ap.parse_args()

    rows = load_added()
    if a.clear:
        for r in rows:
            if r.get("source", "").startswith(("clothing-dataset", "Fashion Product")):
                (PHOTOS / f"{r['item_id']}.png").unlink(missing_ok=True)
        save_added(
            [r for r in rows if not r.get("source", "").startswith(("clothing-dataset", "Fashion Product"))]
        )
        (PHOTOS / "settings.json").unlink(missing_ok=True)
        print("imported items removed")
        return

    from bo.bo7_sharing.demo import cutout  # backend package (path added above)

    rng = random.Random(a.seed)
    gen = (
        candidates_clothing(rng, a.per_class)
        if a.source == "clothing"
        else candidates_products(rng, a.per_class)
    )
    done: dict[str, int] = {}
    known = {r["item_id"] for r in rows}
    added = rejected = 0
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        for c in gen:
            if done.get(c["key"], 0) >= c["quota"]:
                continue
            item_id = f"ds_{c['category']}_{c['id']}"
            if item_id in known:
                continue
            try:
                data = client.get(c["url"]).raise_for_status().content
                res = cutout.run(data)
            except Exception as e:  # noqa: BLE001
                print("skip", c["url"], e)
                continue
            if not good_cutout(res):
                rejected += 1
                continue
            (PHOTOS / f"{item_id}.png").parent.mkdir(parents=True, exist_ok=True)
            (PHOTOS / f"{item_id}.png").write_bytes(res["png"])
            desc = c.get("description") or describe(res["colors"], c["name"])
            rows.append(
                {
                    "item_id": item_id,
                    "category": c["category"],
                    "subcategory": describe(res["colors"], c["name"]),
                    "colors": res["colors"],
                    "wear_count": rng.randint(0, 12),
                    "description": desc,
                    "source": c["source"],
                    "source_url": c["url"],
                    "dataset": c["meta"],
                }
            )
            known.add(item_id)
            done[c["key"]] = done.get(c["key"], 0) + 1
            added += 1
            print(
                f"+ {item_id:<28} {desc}  ({res['method']}, garment {round(res['fg_ratio'] * 100)}% of photo)"
            )
    save_added(rows)
    if a.hide_mock:
        (PHOTOS / "settings.json").write_text(json.dumps({"hide_mock": True}), encoding="utf-8")
    print(f"\n{added} garments imported, {rejected} photos rejected by the cutout quality check → {PHOTOS}")


if __name__ == "__main__":
    main()
