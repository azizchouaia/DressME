"""Exposes M7 to the orchestrator (M8 / BO8) as a tool; picked up automatically by the registry."""

from langchain_core.tools import StructuredTool

from shared.agent_card import describe

from . import service
from .contract import LocalShopInput
from .identity import CARD


async def _run(**kwargs) -> dict:
    # same agent as the API (FashionCLIP is loaded once); logged as coming from the assistant
    return await service.search(kwargs, channel="orchestrator")


tool = StructuredTool.from_function(
    coroutine=_run,
    name=CARD["name"],
    description=describe(CARD),
    args_schema=LocalShopInput,
)
