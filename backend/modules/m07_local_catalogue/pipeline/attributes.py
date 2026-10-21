"""Attributes the shops do not write, estimated from the product photo (offline, after ingest).

    cd backend
    python -m modules.m07_local_catalogue.pipeline.attributes

Gender: read from the product name or URL when the shop writes it ("Basket femme", gender_source=text).
For the other products FashionCLIP compares the photo with "women's <piece>" and "men's <piece>" prompts
(zero-shot, same model and index as the search). The margin, 100 x the difference of the two cosine
similarities, must reach `gender_photo_margin` (config.yaml), else the gender stays unknown: a wrong
"men" hides a piece from a women's search, an unknown one is only ranked a little lower.

The products whose gender is written are the test set: on them the photo prediction is compared with
the text, and the accuracy per margin goes to ml/data/shops/attributes_report.md.
Writes gender / gender_source back into the cleaned CSV. Re-run it after every clean + ingest.
"""

import argparse
import csv
import json
import logging
from collections import Counter
from datetime import date
from pathlib import Path

import numpy as np

from ..paths import CATALOGUE_CSV, CONFIG, INDEX_DIR, model_source
from ..scraper.clean import COLUMNS
from ..taxonomy import gender_from_text
from .parse import SUBCATEGORY_EN

log = logging.getLogger("localcatalogue.attributes")

# Several phrasings per gender, averaged: one prompt alone is noisy in CLIP models.
_TEMPLATES = {
    "women": ["women's {}", "a photo of a women's {}", "{} for women", "a woman wearing a {}"],
    "men": ["men's {}", "a photo of a men's {}", "{} for men", "a man wearing a {}"],
}
MARGINS = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0]


def gender_prompts(encoder, subcategories) -> dict[tuple[str, str], np.ndarray]:
    """(gender, subcategory) -> averaged, L2-normalised text vector ("men's shirt", "shirt for men"...)."""
    out = {}
    for sub in sorted(set(subcategories)):
        noun = SUBCATEGORY_EN.get(sub, sub)
        for gender, templates in _TEMPLATES.items():
            vec = encoder.encode_texts([t.format(noun) for t in templates]).mean(axis=0)
            out[gender, sub] = vec / max(float(np.linalg.norm(vec)), 1e-12)
    return out


def gender_margins(rows: list[dict], vectors: dict[str, np.ndarray], prompts) -> dict[str, float]:
    """product_id -> 100 x (cos(photo, women's prompt) - cos(photo, men's prompt)); > 0 leans women."""
    return {
        r["product_id"]: 100.0
        * float(
            vectors[r["product_id"]] @ (prompts["women", r["subcategory"]] - prompts["men", r["subcategory"]])
        )
        for r in rows
        if r["product_id"] in vectors
    }


def evaluate(rows: list[dict], margins: dict[str, float], thresholds=MARGINS) -> list[dict]:
    """Photo vs written gender, on the products where the shop writes women or men."""
    labelled = [
        (r["gender"], margins[r["product_id"]])
        for r in rows
        if r["gender_source"] == "text" and r["gender"] in ("women", "men") and r["product_id"] in margins
    ]
    out = []
    for t in thresholds:
        kept = [(g, m) for g, m in labelled if abs(m) >= t]
        correct = sum((m > 0) == (g == "women") for g, m in kept)
        out.append(
            {
                "margin": t,
                "labelled": len(labelled),
                "coverage": len(kept) / len(labelled) if labelled else 0.0,
                "accuracy": correct / len(kept) if kept else 0.0,
            }
        )
    return out


def assign(rows: list[dict], margins: dict[str, float], threshold: float) -> Counter:
    """Gender from the name / URL, else from the photo when the margin is large enough, else unknown.

    The text is read again on every run, so rule fixes apply without re-cleaning; photo guesses are
    recomputed too. Returns the count per (source, gender).
    """
    counts: Counter = Counter()
    for r in rows:
        gender, source = gender_from_text(r["product_name"], r["product_url"]), "text"
        if not gender:
            m = margins.get(r["product_id"])
            gender, source = (
                ("women" if m > 0 else "men", "photo") if m is not None and abs(m) >= threshold else ("", "")
            )
        r["gender"], r["gender_source"] = gender, source
        counts[source or "none", gender or "unknown"] += 1
    return counts


def write_report(path: Path, counts: Counter, evaluation: list[dict], threshold: float) -> None:
    lines = [
        f"# Attributes report — {date.today().isoformat()}",
        "",
        "## Gender per source",
        "",
        "| Source | women | men | unisex | unknown |",
        "|---|---|---|---|---|",
    ]
    for source in ("text", "photo", "none"):
        cells = [str(counts[source, g]) for g in ("women", "men", "unisex", "unknown")]
        lines.append(f"| {source} | " + " | ".join(cells) + " |")
    n = evaluation[0]["labelled"] if evaluation else 0
    lines += [
        "",
        f"## Photo vs written gender ({n} products where the shop writes women or men)",
        "",
        "FashionCLIP zero-shot on the photo, compared with the gender written in the name / URL.",
        "",
        "| Margin | Coverage | Accuracy | |",
        "|---|---|---|---|",
    ]
    for e in evaluation:
        used = "← used" if e["margin"] == threshold else ""
        lines.append(f"| {e['margin']:g} | {e['coverage']:.1%} | {e['accuracy']:.1%} | {used} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _vectors(index_dir: Path) -> dict[str, np.ndarray]:
    ids = json.loads((index_dir / "ids.json").read_text(encoding="utf-8"))
    return dict(zip(ids, np.load(index_dir / "image_embeddings.npy"), strict=True))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--csv", type=Path, default=CATALOGUE_CSV)
    parser.add_argument("--index-dir", type=Path, default=INDEX_DIR)
    parser.add_argument("--model", default=model_source())
    parser.add_argument("--margin", type=float, default=CONFIG["gender_photo_margin"])
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    with args.csv.open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    from .encoder import FashionCLIP

    prompts = gender_prompts(FashionCLIP(args.model), (r["subcategory"] for r in rows))
    margins = gender_margins(rows, _vectors(args.index_dir), prompts)
    for r in rows:  # the test set is what the text says, before any photo guess
        r["gender"] = gender_from_text(r["product_name"], r["product_url"])
        r["gender_source"] = "text" if r["gender"] else ""
    evaluation = evaluate(rows, margins, sorted({*MARGINS, args.margin}))
    counts = assign(rows, margins, args.margin)

    with args.csv.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    write_report(args.csv.parent / "attributes_report.md", counts, evaluation, args.margin)
    for e in evaluation:
        log.info(
            "margin %.1f: coverage %.1f%%, accuracy %.1f%%",
            e["margin"],
            100 * e["coverage"],
            100 * e["accuracy"],
        )
    log.info("gender per source: %s", dict(counts))


if __name__ == "__main__":
    main()
