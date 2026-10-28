"""HTTP endpoints of M5. Included automatically by api/main.py.

Every endpoint is served by service.py (M5's own logic; M1 / M2 / M3 are reached through their clients,
which follow their mock / real switches). Also serves the demo UI on GET /m05/ui.
"""

import stat
from collections.abc import Awaitable
from pathlib import Path
from typing import TypeVar

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, RedirectResponse, Response
from starlette.staticfiles import StaticFiles

from . import looks_svg, mock, service
from .config import load_reference_looks, load_styles
from .contract import (
    AgentChatRequest,
    AgentChatResponse,
    CardsResponse,
    ChooseRequest,
    ExplainResponse,
    FeedbackRequest,
    FeedbackResponse,
    GapsRequest,
    GapsResponse,
    InvalidAnswerError,
    PreferencesRequest,
    ProfileEnvelope,
    ProfileNotFoundError,
    ProfileRequest,
    ProfileResponse,
    RecomputeRequest,
    RecomputeResponse,
    StylesResponse,
)

router = APIRouter(prefix="/m05", tags=["M5 Adaptive style profile"])

UI_DIR = Path(__file__).resolve().parent / "ui"
T = TypeVar("T")


async def _call(result: Awaitable[T]) -> T:
    try:
        return await result
    except ProfileNotFoundError as e:
        raise HTTPException(404, f"not found: {e}") from e
    except InvalidAnswerError as e:
        raise HTTPException(422, str(e)) from e


# --- onboarding -------------------------------------------------------------------------------------


@router.get("/onboarding/swipe-cards", response_model=CardsResponse)
async def onboarding_swipe_cards(user_id: str = Query(min_length=1)):
    """First screen of a new user, no question before it: 10 cards to swipe (answer with POST /feedback,
    source=onboarding). Creates the neutral profile; onboarded once every card is answered."""
    return await _call(service.swipe_cards(user_id))


# --- daily loop --------------------------------------------------------------------------------------


@router.post("/choose", response_model=CardsResponse)
async def choose(req: ChooseRequest):
    """Context + M2 candidates (or M5 asks M2) -> a batch of ordered cards, each logged in bandit_log."""
    return await _call(service.choose(req))


@router.post("/feedback", response_model=FeedbackResponse)
async def feedback(req: FeedbackRequest):
    """One or many reactions (send them in the background, batches welcome)."""
    return await _call(service.feedback(req))


# --- profile for the other BOs ------------------------------------------------------------------------


@router.get("/profile/{user_id}", response_model=ProfileResponse)
async def get_profile(user_id: str):
    return await _call(service.profile(user_id))


@router.delete("/profile/{user_id}")
async def delete_profile(user_id: str):
    """Deletes the M5 profile, bandit and logs of the user (privacy, demo reset)."""
    return await _call(service.delete_profile(user_id))


@router.post("/preferences", response_model=ProfileResponse)
async def preferences(req: PreferencesRequest):
    """'More of / less of' some styles: prior shifted (learning kept), style mix moved one step."""
    return await _call(service.adjust_styles(req))


@router.post("/agent/chat", response_model=AgentChatResponse)
async def agent_chat(req: AgentChatRequest):
    """Style coach agent: LLM + M5 tools (profile, explain, preferences, outfits). 503 when the LLM is down."""
    from .agent import graph

    try:
        return await _call(graph.chat(req))
    except graph.LLMUnavailableError as e:
        raise HTTPException(503, str(e)) from e


@router.get("/explain/{user_id}", response_model=ExplainResponse)
async def explain(user_id: str, log_id: str | None = None, k: int = Query(default=5, ge=1, le=20)):
    """Strongest learned rules; with log_id, why that card scored (for 'why this outfit' and BO8)."""
    return await _call(service.explain(user_id, log_id, k))


@router.get("/styles", response_model=StylesResponse)
async def get_styles():
    return await _call(service.styles_info())


@router.post("/styles/recompute", response_model=RecomputeResponse)
async def styles_recompute(req: RecomputeRequest):
    """After editing styles.json: new style vectors, item mixes recomputed, bandits re-initialised."""
    return await _call(service.recompute(req))


# --- week-1 envelope (BO8 orchestrator) ----------------------------------------------------------------


@router.post("/profile", response_model=ProfileEnvelope)
async def profile_envelope(req: ProfileRequest):
    return await service.profile_envelope(req.model_dump())


@router.post("/gaps", response_model=GapsResponse)
def gaps(req: GapsRequest):
    return mock.gaps(req.model_dump())


# --- demo UI + look pictures --------------------------------------------------------------------------


def _serve(directory: Path, path: str) -> FileResponse:
    full, st = StaticFiles(directory=directory, check_dir=False).lookup_path(path)
    if st is None or not stat.S_ISREG(st.st_mode):
        raise HTTPException(404)
    return FileResponse(full, headers={"Cache-Control": "no-cache"})


@router.get("/ui", include_in_schema=False)
async def ui_index():
    return _serve(UI_DIR, "index.html")


@router.get("/ui/", include_in_schema=False)
async def ui_index_slash():
    return RedirectResponse("/m05/ui")


@router.get("/ui/looks/{look_id}.svg", include_in_schema=False)
async def look_picture(look_id: str):
    look = next((lk for lk in load_reference_looks() if lk.id == look_id), None)
    if look is None:
        raise HTTPException(404)
    styles = load_styles()
    family = styles.family_of(look.style_id) if look.style_id in styles.ids else "casual"
    fam = styles.families.get(family)
    label, colour = (fam.label, fam.colour) if fam else (family, "#888")
    svg = looks_svg.render(look.id, look.title, label, colour, look.art)
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "max-age=3600"})


@router.get("/ui/{path:path}", include_in_schema=False)
async def ui_file(path: str):
    return _serve(UI_DIR, path)
