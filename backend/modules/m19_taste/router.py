"""HTTP door for the taste agent: POST /m19/run."""

from fastapi import APIRouter

from .contract import TasteInput, TasteOutput

router = APIRouter(prefix="/m19", tags=["Taste"])


@router.post("/run", response_model=TasteOutput)
async def run(inp: TasteInput):
    from .agent import TasteAgent

    return await TasteAgent()(inp.model_dump())
