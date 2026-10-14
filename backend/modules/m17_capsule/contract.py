"""M17 input / output. Agree them on day 1, change only through a PR reviewed by the owner.

Every endpoint keeps the team envelope {user_id, payload} -> {result, mocked}; payloads are typed below.
M17 scores nothing itself: outfits are scored by M2 (/m02/score: pretrained OutfitTransformer compatibility,
season weather fit, occasion fit); M17 builds the compatibility graph, optimises the capsule (integer linear
programming) and plans the month (occasions from the M4 calendar when M4 runs).
"""

import datetime as dt

from pydantic import BaseModel, Field

from modules.m02_recommendation.contract import WardrobeItem

SEASONS = ("auto", "spring", "summer", "autumn", "winter")


class CapsulePayload(BaseModel):
    size: int = Field(default=12, ge=4, le=40)  # number of pieces in the capsule
    season: str = "auto"  # auto (from the date) / spring / summer / autumn / winter
    occasions: list[str] = ["casual", "work"]  # the capsule must dress these occasions
    # per category, e.g. {"top": 4, "bottom": 3, "shoes": 2}; None = auto from the size and season
    minimums: dict[str, int] | None = None
    must_include: list[str] = []  # pieces the user wants in it
    exclude_item_ids: list[str] = []
    method: str = "ilp"  # ilp (optimal, HiGHS) / greedy / both (compare)
    plan_days: int = Field(default=30, ge=0, le=92)  # 0 = no plan
    start: dt.date | None = None  # first day of the plan, default today
    items: list[WardrobeItem] | None = None  # inline wardrobe (M1 format); None = load it for user_id
    # calibrated M2 compatibility a valid outfit needs (0.55 = better than 55% of random outfits of its shape)
    min_compatibility: float = Field(default=0.55, ge=0, le=1)


class PlanPayload(BaseModel):
    """Plan days with an existing capsule (its piece ids)."""

    item_ids: list[str]
    season: str = "auto"
    occasions: list[str] = ["casual", "work"]
    plan_days: int = Field(default=30, ge=1, le=92)
    start: dt.date | None = None
    items: list[WardrobeItem] | None = None
    min_compatibility: float = Field(default=0.55, ge=0, le=1)


class CapsuleRequest(BaseModel):
    user_id: str | None = None
    payload: CapsulePayload = CapsulePayload()


class PlanRequest(BaseModel):
    user_id: str | None = None
    payload: PlanPayload


class CapsuleResponse(BaseModel):
    result: dict = {}
    mocked: bool = True
