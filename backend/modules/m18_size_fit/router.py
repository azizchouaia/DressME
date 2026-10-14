"""M18 Size & fit advice: size from body measurements + brand size charts."""

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
