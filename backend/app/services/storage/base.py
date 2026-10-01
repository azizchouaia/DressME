from abc import ABC, abstractmethod


class StorageService(ABC):
    """Object storage abstraction. Keys are provider-agnostic, e.g. `uploads/<user>/<file>.jpg`."""

    @abstractmethod
    def save(self, key: str, data: bytes, content_type: str) -> str:
        """Store `data` under `key` and return its public URL."""

    @abstractmethod
    def read(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def url_for(self, key: str) -> str: ...
