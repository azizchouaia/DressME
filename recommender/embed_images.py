"""Embed a folder of clothing images with FashionCLIP and find similar items.

Phase 2 of the recommender: each image becomes a 512-number vector. Similarity
is cosine distance between those vectors. With --database, the vectors are
stored in Postgres (pgvector) and the nearest items come from SQL.

Examples:
    python embed_images.py --images data/hm/images --limit 5000 --query data/hm/images/012/0123456789.jpg
    python embed_images.py --images data/hm/images --query outfit.jpg --database

H&M images, once downloaded from the Kaggle competition, live in nested folders
named by the article id. Any other folder of jpg/png files works too. The
product id is the file name without its extension.

The installed PyTorch on this PC is the CPU build. The RTX 5070 Ti is unused
until torch is reinstalled from the CUDA wheel listed in requirements.txt.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import numpy as np

MODEL_ID = "patrickjohncyh/fashion-clip"
VECTOR_DIM = 512
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def list_images(root: Path, limit: int | None) -> list[Path]:
    paths = [path for path in root.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES]
    paths.sort()
    if limit is not None:
        return paths[:limit]
    return paths


def load_model():
    import torch
    from transformers import CLIPModel, CLIPProcessor

    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print("FashionCLIP is running on CPU. A few thousand images is the right size for this pass.")
    else:
        print(f"FashionCLIP is running on {torch.cuda.get_device_name(0)}.")
    processor = CLIPProcessor.from_pretrained(MODEL_ID)
    model = CLIPModel.from_pretrained(MODEL_ID).to(device)
    model.eval()
    return model, processor, device


def embed_paths(paths: list[Path], batch_size: int, model, processor, device) -> np.ndarray:
    import torch
    from PIL import Image

    vectors: list[np.ndarray] = []
    for start in range(0, len(paths), batch_size):
        batch_paths = paths[start : start + batch_size]
        images = [Image.open(path).convert("RGB") for path in batch_paths]
        inputs = processor(images=images, return_tensors="pt")
        inputs = {name: value.to(device) for name, value in inputs.items()}
        with torch.no_grad():
            features = model.get_image_features(**inputs)
        if hasattr(features, "pooler_output"):
            features = features.pooler_output
        features = features / features.norm(dim=-1, keepdim=True)
        vectors.append(features.detach().cpu().numpy().astype(np.float32))
        print(f"embedded {min(start + batch_size, len(paths))}/{len(paths)}")
    stacked = np.concatenate(vectors, axis=0)
    if stacked.shape[1] != VECTOR_DIM:
        raise SystemExit(f"Expected {VECTOR_DIM}-d embeddings, got {stacked.shape[1]}.")
    return stacked


def nearest(query: np.ndarray, matrix: np.ndarray, ids: list[str], k: int, skip: str | None) -> list[tuple[str, float]]:
    scores = matrix @ query
    order = np.argsort(-scores)
    found: list[tuple[str, float]] = []
    for index in order:
        item_id = ids[int(index)]
        if item_id == skip:
            continue
        found.append((item_id, float(scores[int(index)])))
        if len(found) == k:
            break
    return found


def save_local(out_dir: Path, ids: list[str], vectors: np.ndarray) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / "embeddings.npy", vectors)
    (out_dir / "ids.txt").write_text("\n".join(ids), encoding="utf-8")


def load_local(out_dir: Path) -> tuple[list[str], np.ndarray]:
    ids = (out_dir / "ids.txt").read_text(encoding="utf-8").splitlines()
    vectors = np.load(out_dir / "embeddings.npy")
    return ids, vectors


def vector_literal(values: np.ndarray) -> str:
    return "[" + ",".join(f"{float(value):.7f}" for value in values) + "]"


def store_postgres(database_url: str, source: str, ids: list[str], vectors: np.ndarray) -> None:
    import psycopg

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            for item_id, vector in zip(ids, vectors, strict=True):
                cursor.execute(
                    """
                    INSERT INTO item_embeddings (source, item_key, embedding)
                    VALUES (%s, %s, %s::vector)
                    ON CONFLICT (source, item_key)
                    DO UPDATE SET embedding = EXCLUDED.embedding
                    """,
                    (source, item_id, vector_literal(vector)),
                )
        connection.commit()


def nearest_postgres(database_url: str, source: str, query: np.ndarray, k: int, skip: str | None) -> list[tuple[str, float]]:
    import psycopg

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT item_key, 1 - (embedding <=> %s::vector) AS similarity
                FROM item_embeddings
                WHERE source = %s AND (%s::text IS NULL OR item_key <> %s)
                ORDER BY embedding <=> %s::vector
                LIMIT %s
                """,
                (vector_literal(query), source, skip, skip, vector_literal(query), k),
            )
            return [(row[0], float(row[1])) for row in cursor.fetchall()]


def database_url_from_env() -> str:
    raw = os.environ.get("DATABASE_URL", "postgresql+psycopg://wardrobe:wardrobe@localhost:5432/smart_wardrobe")
    return raw.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Embed clothing images with FashionCLIP and list similar items.")
    parser.add_argument("--images", type=Path, required=True, help="Folder of product images. Subfolders are included.")
    parser.add_argument("--limit", type=int, default=None, help="Embed at most this many images. Start around 5000 on CPU.")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--query", type=Path, default=None, help="One image to compare against the embedded set.")
    parser.add_argument("--top", type=int, default=20)
    parser.add_argument("--out", type=Path, default=Path("data/embeddings"))
    parser.add_argument("--database", action="store_true", help="Also write vectors to Postgres and search there.")
    parser.add_argument("--source", default="hm", help="Label stored with the vectors, so catalogs stay separate.")
    args = parser.parse_args()

    paths = list_images(args.images, args.limit)
    if not paths:
        raise SystemExit(f"No images found in {args.images}.")
    ids = [path.stem for path in paths]
    print(f"{len(paths)} images")
    model, processor, device = load_model()
    vectors = embed_paths(paths, args.batch_size, model, processor, device)
    save_local(args.out, ids, vectors)
    print(f"saved {args.out / 'embeddings.npy'}")

    if args.database:
        store_postgres(database_url_from_env(), args.source, ids, vectors)
        print("stored vectors in item_embeddings")

    if args.query is None:
        return
    query_vector = embed_paths([args.query], batch_size=1, model=model, processor=processor, device=device)[0]
    skip = args.query.stem if args.query.stem in ids else None
    if args.database:
        matches = nearest_postgres(database_url_from_env(), args.source, query_vector, args.top, skip)
    else:
        matches = nearest(query_vector, vectors, ids, args.top, skip)
    for item_id, score in matches:
        print(f"{score:.3f}  {item_id}")


if __name__ == "__main__":
    main()
