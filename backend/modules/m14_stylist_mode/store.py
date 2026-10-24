"""JSON collections of M14 in ml/data/bo6/m14/ (never git): pros, links, reviews, looks, handoffs.

One file per collection, {id: record}. Swap for Postgres later without changing service.py.
"""

import json
import threading
import uuid
from datetime import UTC, datetime

from . import paths

_lock = threading.Lock()


def now() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class Collection:
    def __init__(self, name: str):
        self.name = name

    @property
    def path(self):
        return paths.data_dir() / f"{self.name}.json"

    def all(self) -> dict[str, dict]:
        path = self.path
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def get(self, key: str) -> dict | None:
        return self.all().get(key)

    def put(self, key: str, record: dict) -> dict:
        with _lock:
            records = self.all()
            records[key] = record
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(records, indent=1, ensure_ascii=False, default=str), "utf-8")
        return record

    def delete(self, key: str) -> bool:
        with _lock:
            records = self.all()
            if records.pop(key, None) is None:
                return False
            self.path.write_text(json.dumps(records, indent=1, ensure_ascii=False, default=str), "utf-8")
        return True

    def find(self, **equal) -> list[dict]:
        return [r for r in self.all().values() if all(r.get(k) == v for k, v in equal.items())]


pros = Collection("pros")
links = Collection("links")
reviews = Collection("reviews")
looks = Collection("looks")
handoffs = Collection("handoffs")
challenges = Collection("challenges")  # local brand challenges sponsored by boutiques (Backup 5)
chats = Collection("chats")  # private conversations, key "<pro_id>__<client_id>"


def chat_key(pro_id: str, client_id: str) -> str:
    return f"{pro_id}__{client_id}"
