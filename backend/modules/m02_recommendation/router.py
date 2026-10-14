"""HTTP endpoints of M2. Included automatically by api/main.py."""

import datetime as dt
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from shared.config import settings

from . import mock, service
from .contract import (
    CompleteRequest,
    OutfitsResponse,
    RecommendRequest,
    RemixRequest,
    ScoreRequest,
    SwapRequest,
)

router = APIRouter(prefix="/m02", tags=["M2 Recommendation engine"])
DEMO = Path(__file__).parent / "demo"


def _impl():
    """M02_USE_MOCK overrides the global USE_MOCKS, so M2 can run for real while other modules stay mocked."""
    flag = os.environ.get("M02_USE_MOCK")
    use_mock = settings.use_mocks if flag is None else flag.lower() in ("1", "true", "yes")
    return mock if use_mock else service


@router.post("/recommend", response_model=OutfitsResponse)
def recommend(req: RecommendRequest):
    """Top-n outfits for the context (outfit of the day = n=1)."""
    return _impl().recommend(req.model_dump())


@router.post("/remix", response_model=OutfitsResponse)
def remix(req: RemixRequest):
    """Alternative made of pieces rarely / never worn together, different from the base outfit."""
    return _impl().remix(req.model_dump())


@router.post("/complete", response_model=OutfitsResponse)
def complete(req: CompleteRequest):
    """Complete with AI: keep the pinned pieces, fill the empty slots."""
    return _impl().complete(req.model_dump())


@router.post("/swap", response_model=OutfitsResponse)
def swap(req: SwapRequest):
    """One-tap swap: best replacements for one slot, the rest of the outfit unchanged."""
    return _impl().swap(req.model_dump())


@router.post("/score", response_model=OutfitsResponse)
def score(req: ScoreRequest):
    """Score given outfits (used by Smart Buy what-if, capsule, builder...)."""
    return _impl().score(req.model_dump())


@router.get("/weather")
def weather(city: str = "Tunis", date: dt.date | None = None):
    from .engine.weather import get_weather

    w, source = get_weather(city, date)
    return {"result": {**w, "city": city, "source": source}, "mocked": False}


# ---- demo page (try the engine in a browser): http://localhost:8000/m02/demo ----
@router.get("/demo", include_in_schema=False)
def demo_page():
    return FileResponse(DEMO / "index.html")


@router.get("/demo/wardrobe/{user_id}", include_in_schema=False)
def demo_wardrobe(user_id: str):
    return service.demo_wardrobe(user_id)


@router.get("/demo/metrics", include_in_schema=False)
def demo_metrics():
    from .engine import artifacts

    if not artifacts.EVAL_METRICS.exists():
        raise HTTPException(404, "run ml/scripts/m02/eval_pretrained.py first")
    return FileResponse(artifacts.EVAL_METRICS)


@router.get("/demo/img/{name}", include_in_schema=False)
def demo_image(name: str):
    from .engine import artifacts

    path = (artifacts.DATASET_IMAGES / name).resolve()
    if path.parent != artifacts.DATASET_IMAGES.resolve() or not path.exists():
        raise HTTPException(404)
    return FileResponse(path)
