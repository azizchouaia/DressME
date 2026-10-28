"""Where cards, PNGs and referral events are kept.

`MemoryShareStore` is the dev / test store (week-1 mock). A Postgres + S3 store can replace it later by
implementing the same methods; the agent and the API do not change.
"""

from datetime import UTC, datetime
from typing import Protocol


class ShareStore(Protocol):
    def save_card(self, meta: dict, png: bytes) -> str: ...
    def get_card(self, card_id: str) -> dict | None: ...
    def get_png(self, card_id: str) -> bytes | None: ...
    def find_by_code(self, code: str) -> dict | None: ...
    def add_open(self, code: str, channel: str = "direct") -> None: ...
    def add_signup(self, code: str, new_user_id: str, channel: str | None = None) -> None: ...
    def events(self, user_id: str | None = None) -> tuple[list[dict], list[dict], list[dict]]: ...


class MemoryShareStore:
    def __init__(self, use_s3: bool = False):
        self.cards: dict[str, dict] = {}
        self.pngs: dict[str, bytes] = {}
        self.opens: list[dict] = []
        self.signups: list[dict] = []
        self.use_s3 = use_s3

    def save_card(self, meta: dict, png: bytes) -> str:
        card_id = meta["card_id"]
        if self.use_s3:
            from shared.storage import upload_bytes

            url = upload_bytes(f"share/{meta['user_id']}/{card_id}.png", png)
        else:
            self.pngs[card_id] = png
            url = f"/m10/cards/{card_id}/image"
        self.cards[card_id] = {**meta, "image_url": url, "created_at": datetime.now(UTC).isoformat()}
        return url

    def get_card(self, card_id: str) -> dict | None:
        return self.cards.get(card_id)

    def get_png(self, card_id: str) -> bytes | None:
        return self.pngs.get(card_id)

    def find_by_code(self, code: str) -> dict | None:
        return next((c for c in self.cards.values() if c["short_code"] == code), None)

    def add_open(self, code: str, channel: str = "direct") -> None:
        self.opens.append({"short_code": code, "channel": channel, "ts": datetime.now(UTC).isoformat()})

    def add_signup(self, code: str, new_user_id: str, channel: str | None = None) -> None:
        if any(s["new_user_id"] == new_user_id for s in self.signups):  # one attribution per user
            return
        opens = sum(1 for o in self.opens if o["short_code"] == code)
        signed = sum(1 for s in self.signups if s["short_code"] == code)
        if signed >= opens:  # a friend has to open the link to sign up: count that visit
            self.add_open(code, channel or "direct")
        if channel is None:  # last-touch attribution: channel of the latest open of this link
            last = next((o for o in reversed(self.opens) if o["short_code"] == code), None)
            channel = last["channel"] if last else "direct"
        self.signups.append({"short_code": code, "new_user_id": new_user_id, "channel": channel})

    def events(self, user_id: str | None = None) -> tuple[list[dict], list[dict], list[dict]]:
        cards = [c for c in self.cards.values() if user_id is None or c["user_id"] == user_id]
        codes = {c["short_code"] for c in cards}
        return (
            cards,
            [o for o in self.opens if o["short_code"] in codes],
            [s for s in self.signups if s["short_code"] in codes],
        )
