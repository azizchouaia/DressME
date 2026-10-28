"""Access to the user's garments, owned by M1 (wardrobe digitiser, BO3).

Rule 4 · never re-implement another module: this file only *reads* garments.
  - `M1Wardrobe` (default, `wardrobe_source: m1`): the real wardrobe, read from M1 in-process;
  - `HttpWardrobe` (`wardrobe_source: http`): the same through M1's HTTP API, if M1 runs as its own service;
  - `MockWardrobe` (`wardrobe_source: mock`): the fixture wardrobe, used by the unit tests.
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


def _sync(coro):
    """Run an async M1 function from the synchronous agent code (also inside the API's event loop)."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class M1Wardrobe:
    """The real wardrobe: garments come from M1 (wardrobe digitiser, BO3), called in-process through M1's
    public API (`items`, `classify`, `update_item`, `delete_item`), mock or real depending on M1's setting.

    `seeder(impl, user_id)` (optional, BO7 demo) fills an empty M1 wardrobe of a demo user once, with the BO7
    demo garments, by calling M1's API too. Only active pieces are returned (pending duplicates, archived,
    sold and donated pieces are not in the wardrobe). Images stored by M1 under /m01/media are read from disk
    so the share cards can draw them; `image_raw` keeps the URL for the browser.
    """

    def __init__(
        self,
        seeder=None,
        seed_users: set[str] | None = None,
        local_brands: set[str] | None = None,
        resolve=None,
    ):
        import threading

        self.seeder = seeder
        self.resolve = resolve  # optional: image URL → (browser URL, local file), for demo photos
        self._lock = threading.Lock()
        self.seed_users = seed_users or set()
        self.local_brands = local_brands or set()
        self._seeded: set[str] = set()

    @staticmethod
    def impl():
        from modules.m01_wardrobe import mock, service
        from modules.m01_wardrobe.config import use_mocks
        from shared.config import settings

        return mock if use_mocks(getattr(settings, "use_mocks", True)) else service

    def _local_path(self, url: str | None) -> str | None:
        if not url or not url.startswith("/m01/media/"):
            return None
        from modules.m01_wardrobe import storage

        p = storage.media_root() / url.removeprefix("/m01/media/")
        return str(p) if p.exists() else None

    def _ensure_seeded(self, user_id: str) -> None:
        if not self.seeder or user_id not in self.seed_users or user_id in self._seeded:
            return
        with self._lock:  # two requests at once must not add the demo garments twice
            if user_id in self._seeded:
                return
            if not self._fetch(user_id):
                _sync(self.seeder(self.impl(), user_id))
            self._seeded.add(user_id)

    def _fetch(self, user_id: str) -> list:
        from modules.m01_wardrobe.contract import ItemsRequest

        return _sync(self.impl().items(ItemsRequest(user_id=user_id))).items

    def items(self, user_id: str) -> list[Garment]:
        self._ensure_seeded(user_id)
        out = []
        for it in self._fetch(user_id):
            if it.status != "active":
                continue
            url = it.image_cutout or it.image_raw
            shown = self.resolve(url) if self.resolve and url else None
            # Tunisian maker: bought in a shop of the local catalogue (M7 store_id) or a known Tunisian brand
            local = it.brand if it.brand in self.local_brands else None
            if it.store_id:
                local = it.store or it.brand
            fields = {k: v for k, v in it.model_dump().items() if k in Garment.model_fields}
            browser, local_file = shown or (url, self._local_path(url) or url)
            fields.update(
                image_raw=browser,  # URL for the browser (/m01/media/..., an M1 asset, a demo photo)
                image_cutout=local_file,  # file the card renderer can open
                local_tag=local,
            )
            out.append(Garment.model_validate(fields))
        return out


class HttpWardrobe:
    """Calls M1. Kept synchronous and tiny on purpose; swap in when M1 ships."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def items(self, user_id: str) -> list[Garment]:
        import httpx

        r = httpx.post(f"{self.base_url}/m01/items", json={"user_id": user_id}, timeout=5)
        r.raise_for_status()
        rows = [g for g in r.json().get("items", []) if g.get("status", "active") == "active"]
        keep = Garment.model_fields
        return [Garment.model_validate({k: v for k, v in g.items() if k in keep}) for g in rows]
