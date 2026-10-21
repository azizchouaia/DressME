"""Input/output of the ChallengesAgent (shared module M15 · Community challenges). Built from shared schemas.

Used by BO7 (“7 days, 7 outfits”), BO4 (style discovery challenges) and BO6 (local brand challenges).
A challenge is a list of rules checked on every daily entry. Entries only send item ids: garment attributes
(category, colours, local tag) come from the wardrobe module M1.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from modules.m10_share_cards.contract import PipelineStep

RuleType = Literal[
    "no_repeat",  # no item worn twice during the challenge
    "color_theme",  # params: colors=[...], mode="all" | "any"
    "category_required",  # params: categories=[...], min=1
    "capsule_limit",  # params: max_distinct=10 (10×10 challenge)
    "local_brand",  # params: min=1 (items with a local brand tag, BO6)
    "min_items",  # params: min=3
]


class ChallengeRule(BaseModel):
    type: RuleType
    params: dict = Field(default_factory=dict)


class Challenge(BaseModel):
    challenge_id: str
    title: str
    description: str
    rules: list[ChallengeRule]
    duration_days: int = Field(ge=1, le=31)
    tags: list[str] = []
    sponsor: str | None = None  # local brand (BO6) sponsoring the challenge
    created_by: str = "dressme"
    start_date: date | None = None  # None = rolling: day 1 is the day the user joins


class ChallengeDraft(BaseModel):
    """A challenge created by a user, a stylist (M14) or a sponsoring local brand (BO6)."""

    title: str = Field(min_length=3, max_length=60)
    description: str = Field(min_length=5, max_length=280)
    rules: list[ChallengeRule] = Field(min_length=1, max_length=5)
    duration_days: int = Field(ge=3, le=31)
    tags: list[str] = Field(default_factory=list, max_length=6)
    sponsor: str | None = Field(None, max_length=40)


class ChallengeView(Challenge):
    participants: int = 0
    joined: bool = False
    feasibility: float | None = Field(default=None, ge=0, le=1)  # can this wardrobe complete it?
    match_score: float | None = None  # recommendation score: P(join and finish) from the ML ranker
    ranker: str | None = None  # "ml" (models/recommender.json) or "formula" (if/else fallback)
    reason: str | None = None


class Post(BaseModel):
    post_id: str
    user_id: str
    challenge_id: str
    day: int
    item_ids: list[str]
    caption: str | None = None
    card_image_url: str | None = None  # from M10 (share agent)
    share_url: str | None = None
    likes: int = 0
    comments: int = 0
    created_at: datetime


class Comment(BaseModel):
    comment_id: str
    post_id: str
    user_id: str
    text: str
    created_at: datetime


class Nudge(BaseModel):
    """A participant the ML model sees at risk of dropping out, with a ready-made outfit to win them back."""

    user_id: str
    next_day: int
    completion_probability: float
    risk: Literal["on_track", "at_risk", "high_risk"]
    suggestion: list[str] = []  # item ids
    suggestion_names: list[str] = []
    message: str


class EntryView(BaseModel):
    day: int
    item_ids: list[str]
    valid: bool
    violations: list[str] = []
    post_id: str | None = None


class Progress(BaseModel):
    challenge_id: str
    user_id: str
    duration_days: int
    days_logged: int
    valid_days: int
    streak: int
    completion: float = Field(ge=0, le=1)
    points: int
    badges: list[str] = []
    next_day: int | None = None
    entries: list[EntryView] = []
    completion_probability: float | None = None  # ML: best of 3 models (models/completion.json)
    risk: Literal["on_track", "at_risk", "high_risk"] | None = None


class EntryResult(BaseModel):
    day: int
    valid: bool
    violations: list[str] = []
    post: Post | None = None
    suggestion: list[str] = []  # item ids that would keep the next day valid
    progress: Progress
    coach_message: str | None = None  # LLM (PE + RAG) or template fallback
    coach_source: Literal["llm", "template"] | None = None
    completion_card_url: str | None = None  # M10 "finisher" card when the last day is logged
    completion_share_url: str | None = None
    pipeline: list[PipelineStep] = []  # Input → Code (if/else · ML · LLM) → Output trace
    retrieved: list[dict] = []  # RAG tips used by the coach
    prompt: str | None = None


class LeaderboardRow(BaseModel):
    rank: int
    user_id: str
    valid_days: int
    likes: int
    score: float


Action = Literal["list", "recommend", "create", "join", "submit", "progress", "leaderboard", "feed"]


class ChallengesInput(BaseModel):
    user_id: str
    action: Action = "recommend"
    challenge_id: str | None = None
    day: int | None = Field(default=None, ge=1)  # default: next day to log
    item_ids: list[str] = []
    caption: str | None = None
    share: bool = True  # create an M10 card + post for a valid entry
    draft: ChallengeDraft | None = None  # for action="create"


class ChallengesOutput(BaseModel):
    challenges: list[ChallengeView] = []
    progress: Progress | None = None
    entry: EntryResult | None = None
    leaderboard: list[LeaderboardRow] = []
    posts: list[Post] = []


# ---- Generic shapes of the team template (POST /m15/challenges) ----
class ChallengesRequest(BaseModel):
    """`payload` = a `ChallengesInput` (see above)."""

    user_id: str | None = None
    payload: dict = {}


class ChallengesResponse(BaseModel):
    result: dict = {}
    mocked: bool = True
