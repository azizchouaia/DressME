from pathlib import Path

from app.services.storage.base import StorageService


class LocalStorage(StorageService):
    """Stores files on disk; FastAPI serves them under `public_base_url`."""

    def __init__(self, root: Path, public_base_url: str) -> None:
        self.root = root.resolve()
        self.public_base_url = public_base_url.rstrip("/")
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError(f"Invalid storage key: {key}")
        return path

    def save(self, key: str, data: bytes, content_type: str) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return self.url_for(key)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def url_for(self, key: str) -> str:
        return f"{self.public_base_url}/{key}"
