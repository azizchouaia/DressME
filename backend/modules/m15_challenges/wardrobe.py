"""Access to the user's garments, owned by M1 (wardrobe digitiser, BO3).

Rule 4 · never re-implement another module: this file only *reads* garments. `MockWardrobe` serves a demo
Tunisian wardrobe until M1's `POST /m01/items` is live; then `HttpWardrobe` is plugged in
(`wardrobe_source: http` in config.yaml).
"""

import json
from pathlib import Path
from typing import Protocol

from shared.schemas import Garment

DEMO = Path(__file__).parent / "tests" / "fixtures" / "wardrobe.json"
# Real garment photos of the BO7 demo (dataset photos + Tunisian pieces), used while M1 is mocked.
PHOTOS = Path(__file__).resolve().parents[2] / "bo" / "bo7_sharing" / "demo_wardrobe"


class WardrobeProvider(Protocol):
    def items(self, user_id: str) -> list[Garment]: ...


class MockWardrobe:
    """Demo wardrobe. With `photos_dir`, real garment photos are used:
    `<photos_dir>/<item_id>.png` gives an existing demo item its photo, and `added.json` lists garments added
    from the /bo7/demo page (photo + category + colours found by K-means)."""

    def __init__(self, path: Path = DEMO, photos_dir: Path | None = None):
        self._raw = json.loads(path.read_text())
        self._extra: dict[str, list[Garment]] = {}
        self.photos_dir = photos_dir

    # ---- real photos (demo) ------------------------------------------------------------------
    def photo_path(self, item_id: str) -> Path | None:
        if not self.photos_dir:
            return None
        p = self.photos_dir / f"{item_id}.png"
        return p if p.exists() else None

    def _added(self) -> list[dict]:
        f = self.photos_dir / "added.json" if self.photos_dir else None
        return json.loads(f.read_text(encoding="utf-8")) if f and f.exists() else []

    def _save_added(self, rows: list[dict]) -> None:
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        (self.photos_dir / "added.json").write_text(
            json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8"
        )

    def save_photo(self, item_id: str, png: bytes, meta: dict | None = None) -> None:
        """Store a cutout; `meta` (category, subcategory, colors) creates a new garment if the id is new."""
        if not self.photos_dir:
            raise RuntimeError("photos are disabled for this wardrobe")
        self.photos_dir.mkdir(parents=True, exist_ok=True)
        (self.photos_dir / f"{item_id}.png").write_bytes(png)
        if meta is not None:
            rows = [r for r in self._added() if r["item_id"] != item_id]
            if not any(r["item_id"] == item_id for r in self._raw):
                rows.append({"item_id": item_id, **meta})
                self._save_added(rows)

    def delete(self, item_id: str) -> bool:
        removed = False
        p = self.photo_path(item_id)
        if p:
            p.unlink()
            removed = True
        rows = self._added()
        if any(r["item_id"] == item_id for r in rows):
            self._save_added([r for r in rows if r["item_id"] != item_id])
            removed = True
        return removed

    def hide_mock(self) -> bool:
        f = self.photos_dir / "settings.json" if self.photos_dir else None
        return bool(f and f.exists() and json.loads(f.read_text()).get("hide_mock"))

    def is_added(self, item_id: str) -> bool:
        return any(r["item_id"] == item_id for r in self._added())

    # ---- provider ------------------------------------------------------------------------------
    def items(self, user_id: str) -> list[Garment]:
        if user_id in self._extra:
            return self._extra[user_id]
        out = []
        for r in [*self._raw, *self._added()]:
            photo = self.photo_path(r["item_id"])
            if not photo and self.hide_mock():
                continue  # dataset mode: only pieces with a photo (dataset + Tunisian illustrations)
            raw = str(photo) if photo else f"s3://dressme/demo/{r['item_id']}.jpg"
            out.append(
                Garment(user_id=user_id, image_raw=raw, image_cutout=str(photo) if photo else None, **r)
            )
        return out

    def set_items(self, user_id: str, items: list[Garment]) -> None:  # tests / demos
        self._extra[user_id] = items


class HttpWardrobe:
    """Calls M1. Kept synchronous and tiny on purpose; swap in when M1 ships."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def items(self, user_id: str) -> list[Garment]:
        import httpx

        r = httpx.post(f"{self.base_url}/m01/items", json={"user_id": user_id, "payload": {}}, timeout=5)
        r.raise_for_status()
        result = r.json().get("result", {})
        rows = result.get("items", []) if isinstance(result, dict) else result
        return [Garment.model_validate(g) for g in rows]
