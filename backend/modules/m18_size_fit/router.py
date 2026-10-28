"""M18 Size & fit advice: size from body numbers OR fit words (tight/normal/oversized) + brand size charts."""

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from . import service

router = APIRouter(prefix="/m18", tags=["M18 Size & fit advice"])
DATA = Path(__file__).resolve().parents[3] / "ml" / "data" / "bo5"


class AdviseRequest(BaseModel):
    brand: str
    category: str
    body: dict


@router.post("/advise")
def advise(req: AdviseRequest):
    return {"advice": service.advise(service.load_charts(DATA), req.brand, req.category, req.body)}


@router.get("/fit-options")
def fit_options():
    return {"fit": service.FIT_LABELS, "like_fit": list(service.LIKE_ROOM)}


class FitTextRequest(BaseModel):
    text: str
    use_llm: bool = True


@router.post("/parse-fit")
def parse_fit(req: FitTextRequest):
    """Free text about how clothes fit -> fit facts (brand, size, fit, body part) + how the user likes to wear."""
    from . import text_fit
    brands = [b for b in service.load_charts(DATA) if not b.startswith("_")]
    out = text_fit.parse(req.text, brands, req.use_llm)
    return {**out, "tips": text_fit.part_tips(out["refs"])}


@router.get("/identity")
def identity_card():
    from .identity import CARD
    return CARD
