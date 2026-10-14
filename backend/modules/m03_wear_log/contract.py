"""M3 input / output. Agree them on day 1, change only through a PR reviewed by the owner.

Every endpoint keeps the team envelope {user_id, payload} -> {result, mocked}; payloads are typed below.
M3 does not own the pieces (M1 does): it only stores what happened to item ids — worn when, status now.
"""

import datetime as dt
from enum import StrEnum

from pydantic import BaseModel, Field


class ItemStatus(StrEnum):
    available = "available"
    laundry = "laundry"
    lent = "lent"


# ---------- payloads ----------
class WornPayload(BaseModel):
    """Log "worn today" (or another day) for a set of pieces."""

    item_ids: list[str]
    date: dt.date | None = None  # default today
    outfit_id: str | None = None  # M2 outfit id when the user wore a suggestion
    posted: bool = False  # shared on social media: never re-suggest this exact look
    source: str = "manual"  # manual / suggestion / chat / import
    auto_laundry_after: int = 0  # move a top / bottom / dress to the laundry after N wears (0 = off)
    laundry_categories: dict[str, str] = {}  # item_id -> category, to apply auto-laundry to clothes only


class UnwornPayload(BaseModel):
    entry_id: str  # undo a wrong "worn" log


class PostedPayload(BaseModel):
    entry_id: str
    posted: bool = True


class StatusPayload(BaseModel):
    item_ids: list[str]
    status: ItemStatus
    lent_to: str | None = None
    expected_back: dt.date | None = None
    note: str | None = None


class LaundryDonePayload(BaseModel):
    item_ids: list[str] | None = None  # None = everything in the laundry is clean again


class QueryPayload(BaseModel):
    item_ids: list[str] | None = None  # the wardrobe (from M1); needed to list never-worn pieces
    today: dt.date | None = None  # default today (handy for tests and demos)
    laundry_reminder_days: int = 3  # "Back in your closet?" after this many days in the laundry


class StatsPayload(QueryPayload):
    pass


class HistoryPayload(BaseModel):
    since: dt.date | None = None
    until: dt.date | None = None
    item_id: str | None = None  # only entries containing this piece
    limit: int = Field(default=500, ge=1, le=5000)


class ForgottenPayload(QueryPayload):
    days: int = 60  # not worn for at least this many days (never-worn pieces included)


class RecapPayload(BaseModel):
    month: str | None = None  # "2026-10"; default the current month
    item_ids: list[str] | None = None


# ---------- results ----------
class WearEntry(BaseModel):
    entry_id: str
    date: dt.date
    item_ids: list[str]
    outfit_key: str  # sorted item ids: same key = exact same outfit
    outfit_id: str | None = None
    posted: bool = False
    source: str = "manual"


class ItemState(BaseModel):
    item_id: str
    status: ItemStatus = ItemStatus.available
    status_since: dt.date | None = None
    lent_to: str | None = None
    expected_back: dt.date | None = None
    note: str | None = None
    wears_since_wash: int = 0
    reminder: str | None = None  # "back_in_closet?" / "lent_overdue"


class ItemStats(ItemState):
    wear_count: int = 0
    last_worn: dt.date | None = None
    first_worn: dt.date | None = None
    days_since_worn: int | None = None  # None = never worn
    wears_30d: int = 0
    wears_90d: int = 0


class WardrobeSummary(BaseModel):
    pieces: int  # pieces known (wardrobe ids given + pieces ever logged)
    worn_30d: int  # distinct pieces worn in the last 30 days
    utilisation_30d: float  # worn_30d / pieces
    never_worn: list[str]
    forgotten_60d: list[str]
    most_worn: list[str]
    in_laundry: list[str]
    lent: list[str]
    outfits_logged: int
    repeated_outfits_30d: int  # same exact outfit worn more than once in 30 days


class Recap(BaseModel):
    month: str
    days_logged: int
    wears: int
    distinct_pieces: int
    utilisation: float | None = None  # distinct_pieces / wardrobe size, when item_ids are given
    top_pieces: list[dict]  # [{item_id, wears}]
    first_time_worn: list[str]  # pieces worn for the first time this month
    repeated_outfits: list[dict]  # [{item_ids, times}]
    posted_looks: int


# ---------- envelopes ----------
class _Req(BaseModel):
    user_id: str | None = None


class WornRequest(_Req):
    payload: WornPayload


class UnwornRequest(_Req):
    payload: UnwornPayload


class PostedRequest(_Req):
    payload: PostedPayload


class StatusRequest(_Req):
    payload: StatusPayload


class LaundryDoneRequest(_Req):
    payload: LaundryDonePayload = LaundryDonePayload()


class StatesRequest(_Req):
    payload: QueryPayload = QueryPayload()


class StatsRequest(_Req):
    payload: StatsPayload = StatsPayload()


class HistoryRequest(_Req):
    payload: HistoryPayload = HistoryPayload()


class ForgottenRequest(_Req):
    payload: ForgottenPayload = ForgottenPayload()


class RecapRequest(_Req):
    payload: RecapPayload = RecapPayload()


class Response(BaseModel):
    result: dict = {}
    mocked: bool = True


# Names kept from the week-0 skeleton.
WornResponse = StatsResponse = Response
