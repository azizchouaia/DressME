"""HTTP endpoints of M15 · Community challenges (owner BO7). Included automatically by api/main.py.

- `POST /m15/challenges`: generic endpoint of the team template (`ChallengesRequest` → `ChallengesResponse`);
  `payload` is a `ChallengesInput` (action: list, recommend, create, join, submit, progress, leaderboard...).
- REST endpoints under `/m15/challenges/...` used by the BO7 screens and by BO4 / BO6.
"""

import inspect

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from shared.base_agent import AgentError

from . import mock
from .contract import (
    ChallengeDraft,
    ChallengesRequest,
    ChallengesResponse,
    ChallengeView,
    Comment,
    EntryResult,
    LeaderboardRow,
    Nudge,
    Post,
    Progress,
)

try:  # needs the M10 deps (cards, RAG) listed in modules/m10_share_cards/requirements.txt
    from . import service
    from .singleton import challenges_agent
except ImportError as _e:  # pragma: no cover - depends on the environment
    service, challenges_agent, _MISSING = None, None, str(_e)
else:
    _MISSING = None

router = APIRouter(prefix="/m15", tags=["M15 Community challenges"])


@router.get("/identity")
def identity_card():
    from .identity import CARD
    return CARD


class _Lazy:
    def __getattr__(self, name):
        if challenges_agent is None:
            raise HTTPException(
                503, f"M15 needs: pip install -r modules/m15_challenges/requirements.txt ({_MISSING})"
            )
        return getattr(challenges_agent, name)


agent = _Lazy()


def _impl():
    """service.py is ready, so it is served even while USE_MOCKS=true; the mock stays as a fallback."""
    return service if service is not None else mock


@router.post("/challenges", response_model=ChallengesResponse)
async def challenges(req: ChallengesRequest):
    out = _impl().challenges(req.model_dump())
    return await out if inspect.isawaitable(out) else out


class UserBody(BaseModel):
    user_id: str


class EntryBody(BaseModel):
    user_id: str
    item_ids: list[str]
    day: int | None = Field(default=None, ge=1)
    caption: str | None = None
    share: bool = True


def _bad(e: AgentError) -> HTTPException:
    msg = str(e)
    return HTTPException(404 if msg.startswith(("Unknown", "Not in")) else 400, msg)


@router.get("/challenges", response_model=list[ChallengeView])
async def list_challenges(user_id: str, recommended: bool = True):
    return agent.recommend(user_id) if recommended else agent.list_challenges(user_id)


class CreateBody(ChallengeDraft):
    user_id: str


@router.post("/challenges/create", response_model=ChallengeView, status_code=201)
async def create_challenge(body: CreateBody):
    """Publish a new challenge (user, stylist M14, sponsoring local brand BO6). Rules are validated."""
    try:
        return agent.create_challenge(body.user_id, ChallengeDraft(**body.model_dump(exclude={"user_id"})))
    except AgentError as e:
        raise _bad(e) from e


@router.get("/challenges/posts/all", response_model=list[Post])
async def all_posts():
    return agent.feed(None)


class CommentBody(BaseModel):
    user_id: str
    text: str


@router.get("/challenges/posts/{post_id}/comments", response_model=list[Comment])
async def list_comments(post_id: str):
    try:
        return agent.comments(post_id)
    except AgentError as e:
        raise _bad(e) from e


@router.post("/challenges/posts/{post_id}/comments", response_model=Comment, status_code=201)
async def add_comment(post_id: str, body: CommentBody):
    """Comment on a post. if/else moderation refuses links, shouting and hurtful words (400 + reason)."""
    try:
        return agent.comment(post_id, body.user_id, body.text)
    except AgentError as e:
        raise _bad(e) from e


@router.post("/challenges/posts/{post_id}/like")
async def like_post(post_id: str, body: UserBody):
    try:
        return {"post_id": post_id, "likes": agent.like(post_id, body.user_id)}
    except AgentError as e:
        raise _bad(e) from e


@router.get("/challenges/{challenge_id}", response_model=ChallengeView)
async def get_challenge(challenge_id: str, user_id: str):
    view = next((c for c in agent.list_challenges(user_id) if c.challenge_id == challenge_id), None)
    if view is None:
        raise HTTPException(404, f"Unknown challenge {challenge_id!r}")
    return view


@router.post("/challenges/{challenge_id}/join", response_model=Progress)
async def join(challenge_id: str, body: UserBody):
    try:
        return agent.join(body.user_id, challenge_id)
    except AgentError as e:
        raise _bad(e) from e


@router.post("/challenges/{challenge_id}/entries", response_model=EntryResult)
async def submit_entry(challenge_id: str, body: EntryBody):
    try:
        return await agent.submit(
            body.user_id, challenge_id, body.item_ids, body.day, body.caption, body.share
        )
    except AgentError as e:
        raise _bad(e) from e


@router.get("/challenges/{challenge_id}/progress", response_model=Progress)
async def get_progress(challenge_id: str, user_id: str):
    try:
        return agent.progress(user_id, challenge_id)
    except AgentError as e:
        raise _bad(e) from e


@router.get("/challenges/{challenge_id}/nudges", response_model=list[Nudge])
async def nudges(challenge_id: str, all: bool = False):
    """ML: who is likely to drop out (lowest P(finish) first) + an outfit to send them as a reminder."""
    try:
        return agent.nudges(challenge_id, include_on_track=all)
    except AgentError as e:
        raise _bad(e) from e


@router.get("/challenges/{challenge_id}/leaderboard", response_model=list[LeaderboardRow])
async def get_leaderboard(challenge_id: str):
    try:
        return agent.leaderboard(challenge_id)
    except AgentError as e:
        raise _bad(e) from e


@router.get("/challenges/{challenge_id}/posts", response_model=list[Post])
async def challenge_posts(challenge_id: str):
    return agent.feed(challenge_id)
