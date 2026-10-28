"""Knowledge base: the cleaned catalogue CSV plus its FashionCLIP index, loaded once at startup."""

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..scraper.normalize import fold
from .context import is_casual, season_hint
from .retrieve import BM25, tokenize


def _product(row: dict) -> dict:
    row = dict(row)
    row["price_tnd"] = float(row["price_tnd"]) if row.get("price_tnd") else None
    row["available"] = str(row.get("available", "")).lower() == "true"
    return row


@dataclass
class Catalogue:
    products: list[dict]
    embeddings: np.ndarray  # (N, dim) L2-normalised; zero rows where a product has no photo embedding
    has_embedding: np.ndarray = field(init=False)
    bm25: BM25 = field(init=False)

    def __post_init__(self) -> None:
        self.has_embedding = np.linalg.norm(self.embeddings, axis=1) > 0
        self.bm25 = BM25([tokenize(self.document(p)) for p in self.products])
        self.price = np.array(
            [p["price_tnd"] if p["price_tnd"] is not None else np.nan for p in self.products]
        )
        self.available = np.array([p["available"] for p in self.products], dtype=bool)
        self.category = np.array([p["category"] for p in self.products], dtype=object)
        self.subcategory = np.array([p["subcategory"] for p in self.products], dtype=object)
        self.color = np.array([p.get("color") or "" for p in self.products], dtype=object)
        self.gender = np.array([p.get("gender") or "" for p in self.products], dtype=object)
        self.governorates = [set(filter(None, p.get("governorate", "").split("; "))) for p in self.products]
        self.cities = [set(filter(None, p.get("city", "").split("; "))) for p in self.products]
        # +1 summer piece, -1 winter piece, 0 neither (name words + type): re-ranks a seasonal request
        # (the photo's season, attributes.py, fills in when the name and the type say nothing)
        photo = {"summer": 1, "winter": -1}
        self.season = np.array(
            [
                season_hint(fold(p.get("product_name", "")), p.get("subcategory", ""))
                or (photo.get(p.get("season", ""), 0) if p.get("season_source") == "photo" else 0)
                for p in self.products
            ]
        )
        self.row_of = {p["product_id"]: i for i, p in enumerate(self.products)}
        self.casual = np.array(
            [is_casual(fold(p.get("product_name", "")), p.get("subcategory", "")) for p in self.products]
        )
        # newest check of the shops' pages (YYYY-MM-DD): prices and stock are as of this day
        self.checked_on = max((p.get("last_checked") or "" for p in self.products), default="") or None
        # Words actually used by the shops (names, labels, colours, shop names): targets for typo correction.
        self.vocabulary = {
            w for p in self.products for w in re.findall(r"\w+", fold(self.document(p))) if len(w) >= 3
        }

    def __len__(self) -> int:
        return len(self.products)

    @staticmethod
    def document(p: dict) -> str:
        """Text indexed by BM25 (FR display label + EN codes so both languages hit)."""
        return " ".join(
            str(p.get(k) or "")
            for k in ("product_name", "label_fr", "subcategory", "color_fr", "color", "shop_name", "city")
        )

    @classmethod
    def from_records(cls, records: list[dict], embeddings: np.ndarray | None = None, dim: int = 512):
        products = [_product(r) for r in records]
        if embeddings is None:
            embeddings = np.zeros((len(products), dim), np.float32)
        return cls(products, embeddings.astype(np.float32))

    @classmethod
    def load(cls, csv_path: Path, index_dir: Path | None = None, dim: int = 512) -> "Catalogue":
        with Path(csv_path).open(encoding="utf-8-sig") as fh:
            records = list(csv.DictReader(fh))
        embeddings = np.zeros((len(records), dim), np.float32)
        if index_dir and (Path(index_dir) / "image_embeddings.npy").exists():
            vectors = np.load(Path(index_dir) / "image_embeddings.npy")
            ids = json.loads((Path(index_dir) / "ids.json").read_text(encoding="utf-8"))
            row_of = {pid: i for i, pid in enumerate(ids)}
            for i, r in enumerate(records):
                if r["product_id"] in row_of:  # products added since the last ingest keep a zero vector
                    embeddings[i] = vectors[row_of[r["product_id"]]]
        return cls.from_records(records, embeddings, dim)
