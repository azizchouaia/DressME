"""Load the cleaned shop catalogue into the index: one FashionCLIP embedding per product photo (offline).

    cd backend
    python -m modules.m07_local_catalogue.pipeline.ingest

Writes ml/data/shops/index/image_embeddings.npy (N x 512, float32, L2-normalised), ids.json
(product_id of each row) and meta.json. Re-run it after every scrape + clean; products without
an embedding are still searchable by text and filters, only the visual part of their score is missing.

Incremental: products already in the index (same product_id = same photo, same model) are reused, only
new ones go through FashionCLIP. --full re-encodes everything (e.g. after changing the model).
"""

import argparse
import csv
import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ..paths import CATALOGUE_CSV, INDEX_DIR, model_source

log = logging.getLogger("localcatalogue.ingest")


def _previous_index(index_dir: Path, model: str) -> dict[str, np.ndarray]:
    """product_id -> vector of the existing index, if it was built with the same model."""
    try:
        meta = json.loads((index_dir / "meta.json").read_text(encoding="utf-8"))
        if meta.get("model") != model:
            return {}
        ids = json.loads((index_dir / "ids.json").read_text(encoding="utf-8"))
        return dict(zip(ids, np.load(index_dir / "image_embeddings.npy"), strict=True))
    except (OSError, ValueError):
        return {}


def build_index(csv_path: Path, index_dir: Path, encoder, batch_size: int = 32, reuse: bool = True) -> dict:
    with csv_path.open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    data_dir = csv_path.parent
    usable = [r for r in rows if r.get("image_path") and (data_dir / r["image_path"]).is_file()]
    model = getattr(encoder, "model_name", type(encoder).__name__)
    previous = _previous_index(index_dir, model) if reuse else {}
    todo = [r for r in usable if r["product_id"] not in previous]
    log.info(
        "%d products, %d with a photo, %d to encode, %d reused",
        len(rows),
        len(usable),
        len(todo),
        len(usable) - len(todo),
    )

    started = time.perf_counter()
    fresh = encoder.encode_images([data_dir / r["image_path"] for r in todo], batch_size=batch_size)
    new_vectors = dict(zip((r["product_id"] for r in todo), fresh, strict=True))
    vectors = (
        np.stack([previous.get(r["product_id"], new_vectors.get(r["product_id"])) for r in usable])
        if usable
        else np.zeros((0, getattr(encoder, "dim", 512)), np.float32)
    )
    index_dir.mkdir(parents=True, exist_ok=True)
    np.save(index_dir / "image_embeddings.npy", vectors)
    (index_dir / "ids.json").write_text(json.dumps([r["product_id"] for r in usable]), encoding="utf-8")
    meta = {
        "model": model,
        "dim": int(vectors.shape[1]) if len(vectors) else 0,
        "products": len(rows),
        "embedded": len(usable),
        "encoded_now": len(todo),
        "catalogue_csv": csv_path.name,
        "built_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "seconds": round(time.perf_counter() - started, 1),
    }
    (index_dir / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--csv", type=Path, default=CATALOGUE_CSV)
    parser.add_argument("--index-dir", type=Path, default=INDEX_DIR)
    parser.add_argument("--model", default=model_source())
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument(
        "--full", action="store_true", help="re-encode every photo (ignore the existing index)"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    from .encoder import FashionCLIP

    meta = build_index(
        args.csv, args.index_dir, FashionCLIP(args.model), args.batch_size, reuse=not args.full
    )
    log.info("index ready: %s", meta)


if __name__ == "__main__":
    main()
