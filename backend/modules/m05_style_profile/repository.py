"""M5 state: records + the in-memory store. store_pg.py has the same methods on PostgreSQL.

Tables (spec 5): style_profile, item_style, bandit_state, bandit_log, reference_look.
config `storage`: auto -> postgres when M1 is real (it already needs the database), memory otherwise.
"""

import datetime as dt
import uuid
from dataclasses import dataclass, field, replace

from .bandit import LinearTS


def now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def new_log_id() -> str:
    return f"lg_{uuid.uuid4().hex[:16]}"


@dataclass
class ProfileRecord:
    user_id: str
    # want_more / want_less (/preferences); "_" keys are internal: _onboarding_open (log ids of the
    # onboarding batch not answered yet), _n_liked (positive reactions learnt, for the taste learning rate)
    answers: dict = field(default_factory=dict)
    style_mix: dict = field(default_factory=dict)
    taste_vector: list[float] | None = None
    # Rocchio (ranking: rocchio): running sums of the liked / rejected card embeddings, weighted by source
    liked_sum: list[float] | None = None
    n_liked: float = 0.0
    rejected_sum: list[float] | None = None
    n_rejected: float = 0.0
    onboarded: bool = False
    created_at: dt.datetime | None = None
    updated_at: dt.datetime | None = None


@dataclass
class BanditRecord:
    user_id: str
    model: LinearTS
    styles_version: str
    updated_at: dt.datetime | None = None


@dataclass
class LogRecord:
    log_id: str
    user_id: str
    context: dict
    features: list[float]
    source: str
    outfit_id: str | None = None
    look_id: str | None = None
    item_ids: list[str] = field(default_factory=list)
    rank: int | None = None
    score: float | None = None
    shown_at: dt.datetime | None = None
    reward: float | None = None
    reaction: str | None = None
    rewarded_at: dt.datetime | None = None


@dataclass
class LookRecord:
    id: str
    style_id: str
    family: str
    title: str
    description: str
    image_url: str
    primary: bool
    formality: float
    warmth: float
    embedding: list[float]
    version: str


class MemoryStore:
    """Process memory (mock mode, tests). Same async methods as store_pg.PgStore."""

    def __init__(self):
        self.profiles: dict[str, ProfileRecord] = {}
        self.item_styles: dict[str, tuple[list[float], str]] = {}
        self.bandits: dict[str, BanditRecord] = {}
        self.logs: dict[str, LogRecord] = {}
        self.looks: list[LookRecord] = []

    # profiles
    async def get_profile(self, user_id: str) -> ProfileRecord | None:
        p = self.profiles.get(user_id)
        return replace(p, answers=dict(p.answers)) if p else None

    async def save_profile(self, p: ProfileRecord) -> ProfileRecord:
        p.created_at = p.created_at or now()
        p.updated_at = now()
        self.profiles[p.user_id] = replace(p)
        return p

    async def delete_user(self, user_id: str) -> bool:
        found = self.profiles.pop(user_id, None) is not None
        found |= self.bandits.pop(user_id, None) is not None
        for log_id in [k for k, v in self.logs.items() if v.user_id == user_id]:
            del self.logs[log_id]
        return found

    # item styles
    async def get_item_styles(self, item_ids: list[str], version: str) -> dict[str, list[float]]:
        return {
            i: self.item_styles[i][0]
            for i in item_ids
            if i in self.item_styles and self.item_styles[i][1] == version
        }

    async def save_item_styles(self, mixes: dict[str, list[float]], version: str) -> None:
        for i, m in mixes.items():
            self.item_styles[i] = (list(m), version)

    async def drop_stale_item_styles(self, version: str) -> int:
        stale = [i for i, (_, v) in self.item_styles.items() if v != version]
        for i in stale:
            del self.item_styles[i]
        return len(stale)

    # bandit
    async def get_bandit(self, user_id: str) -> BanditRecord | None:
        r = self.bandits.get(user_id)
        return (
            BanditRecord(r.user_id, LinearTS.from_dict(r.model.to_dict()), r.styles_version, r.updated_at)
            if r
            else None
        )

    async def save_bandit(self, r: BanditRecord) -> None:
        r.updated_at = now()
        self.bandits[r.user_id] = BanditRecord(
            r.user_id, LinearTS.from_dict(r.model.to_dict()), r.styles_version, r.updated_at
        )

    # log
    async def add_logs(self, logs: list[LogRecord]) -> None:
        for lg in logs:
            lg.shown_at = lg.shown_at or now()
            self.logs[lg.log_id] = replace(lg)

    async def get_log(self, user_id: str, log_id: str) -> LogRecord | None:
        lg = self.logs.get(log_id)
        return replace(lg) if lg and lg.user_id == user_id else None

    async def find_open_log(
        self, user_id: str, outfit_id: str | None, look_id: str | None
    ) -> LogRecord | None:
        found = [
            lg
            for lg in self.logs.values()
            if lg.user_id == user_id
            and lg.reward is None
            and ((outfit_id and lg.outfit_id == outfit_id) or (look_id and lg.look_id == look_id))
        ]
        return replace(max(found, key=lambda lg: lg.shown_at)) if found else None

    async def set_reward(self, lg: LogRecord) -> None:
        self.logs[lg.log_id] = replace(lg)

    async def count_feedback(self, user_id: str) -> int:
        return sum(1 for lg in self.logs.values() if lg.user_id == user_id and lg.reward is not None)

    # reference looks
    async def get_looks(self, version: str) -> list[LookRecord]:
        return [replace(lk) for lk in self.looks if lk.version == version]

    async def save_looks(self, looks: list[LookRecord]) -> None:
        self.looks = [replace(lk) for lk in looks]


_stores: dict[str, object] = {}


def get_store():
    """MemoryStore or PgStore, following config `storage` (env M05_STORE)."""
    from . import m01_client
    from .config import get_config

    kind = get_config().storage
    if kind == "auto":
        kind = "postgres" if m01_client.mode() == "real" else "memory"
    if kind not in _stores:
        if kind == "postgres":
            from .store_pg import PgStore

            _stores[kind] = PgStore()
        elif kind == "memory":
            _stores[kind] = MemoryStore()
        else:
            raise ValueError(f"unknown M5 storage {kind!r} (auto | memory | postgres)")
    return _stores[kind]


def _reset() -> None:
    """Tests only: forget the in-memory state."""
    _stores.pop("memory", None)
