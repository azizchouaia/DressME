"""HTTP endpoints of M3. Included automatically by api/main.py."""

import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from shared.config import settings

from . import mock, service
from .contract import (
    ForgottenRequest,
    HistoryRequest,
    LaundryDoneRequest,
    PostedRequest,
    RecapRequest,
    Response,
    StatesRequest,
    StatsRequest,
    StatusRequest,
    UnwornRequest,
    WornRequest,
)

router = APIRouter(prefix="/m03", tags=["M3 Wear log + item status"])
DEMO = Path(__file__).parent / "demo"


def _impl():
    """M03_USE_MOCK overrides the global USE_MOCKS, so M3 can run for real while other modules stay mocked."""
    flag = os.environ.get("M03_USE_MOCK")
    use_mock = settings.use_mocks if flag is None else flag.lower() in ("1", "true", "yes")
    return mock if use_mock else service


@router.post("/worn", response_model=Response)
def worn(req: WornRequest):
    """Log pieces as worn (today by default). Optional auto-laundry after N wears."""
    return _impl().worn(req.model_dump())


@router.post("/unworn", response_model=Response)
def unworn(req: UnwornRequest):
    """Undo a "worn" log."""
    return _impl().unworn(req.model_dump())


@router.post("/posted", response_model=Response)
def posted(req: PostedRequest):
    """Mark a logged look as posted on social media (M2 never re-suggests it)."""
    return _impl().posted(req.model_dump())


@router.post("/status", response_model=Response)
def status(req: StatusRequest):
    """Set pieces to available / laundry / lent."""
    return _impl().status(req.model_dump())


@router.post("/laundry_done", response_model=Response)
def laundry_done(req: LaundryDoneRequest):
    """Everything (or item_ids) in the laundry is back in the closet."""
    return _impl().laundry_done(req.model_dump())


@router.post("/states", response_model=Response)
def states(req: StatesRequest):
    """Current status of the pieces + reminders ("back in your closet?", lent overdue)."""
    return _impl().states(req.model_dump())


@router.post("/stats", response_model=Response)
def stats(req: StatsRequest):
    """Per piece: wear count, last worn, days since worn, status. Wardrobe summary."""
    return _impl().stats(req.model_dump())


@router.post("/history", response_model=Response)
def history(req: HistoryRequest):
    """Wear log, newest first (the `wear_log` format M2 takes)."""
    return _impl().history(req.model_dump())


@router.post("/forgotten", response_model=Response)
def forgotten(req: ForgottenRequest):
    """Pieces not worn for N days (never-worn pieces included when item_ids are given)."""
    return _impl().forgotten(req.model_dump())


@router.post("/recap", response_model=Response)
def recap(req: RecapRequest):
    """Monthly recap: wears, distinct pieces, top pieces, first-time pieces, repeated outfits."""
    return _impl().recap(req.model_dump())


# ---- demo page: http://localhost:8000/m03/demo ----
@router.get("/demo", include_in_schema=False)
def demo_page():
    return FileResponse(DEMO / "index.html")


@router.post("/demo/seed/{user_id}", include_in_schema=False)
def demo_seed(user_id: str):
    """Reset a demo user and import a synthetic 120-day wear log for the M2 demo wardrobe."""
    import datetime as dt

    from modules.m02_recommendation.engine import wardrobe

    service.reset(user_id)
    items = wardrobe.load_demo(user_id)
    n = service.seed(user_id, wardrobe.demo_wear_log(user_id, items, dt.date.today()))
    return {"result": {"user_id": user_id, "entries": n}, "mocked": False}
