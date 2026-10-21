"""Incremental index: photos already embedded are reused, only new products are encoded."""

import csv
import json

import numpy as np
from PIL import Image

from modules.m07_local_catalogue.pipeline.ingest import build_index


class CountingEncoder:
    model_name = "fake-clip"
    dim = 4

    def __init__(self):
        self.encoded: list[str] = []

    def encode_images(self, paths, batch_size=32):
        self.encoded += [p.name for p in paths]
        return np.eye(4, dtype=np.float32)[[hash(p.name) % 4 for p in paths]] if paths else np.zeros((0, 4))


def write_catalogue(path, ids):
    (path.parent / "images").mkdir(exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=["product_id", "image_path"])
        w.writeheader()
        for pid in ids:
            Image.new("RGB", (8, 8)).save(path.parent / "images" / f"{pid}.jpg")
            w.writerow({"product_id": pid, "image_path": f"images/{pid}.jpg"})


def test_only_new_products_are_encoded(tmp_path):
    csv_path, index = tmp_path / "catalogue.csv", tmp_path / "index"
    write_catalogue(csv_path, ["a", "b"])
    first = CountingEncoder()
    build_index(csv_path, index, first)
    assert sorted(first.encoded) == ["a.jpg", "b.jpg"]

    write_catalogue(csv_path, ["a", "b", "c"])
    second = CountingEncoder()
    meta = build_index(csv_path, index, second)
    assert second.encoded == ["c.jpg"] and meta["encoded_now"] == 1
    assert json.loads((index / "ids.json").read_text()) == ["a", "b", "c"]
    assert np.load(index / "image_embeddings.npy").shape == (3, 4)

    full = CountingEncoder()
    build_index(csv_path, index, full, reuse=False)
    assert len(full.encoded) == 3
