"""HTTP door for the talk agent: POST /m20/run."""

from fastapi import APIRouter

from .contract import TalkInput, TalkOutput

router = APIRouter(prefix="/m20", tags=["Talk"])


@router.post("/run", response_model=TalkOutput)
async def run(inp: TalkInput):
    from .agent import TalkAgent

    return await TalkAgent()(inp.model_dump())
