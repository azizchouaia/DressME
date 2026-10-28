"""Exposes the taste agent to the orchestrator. The card is the description."""

from langchain_core.tools import StructuredTool

from shared.agent_card import describe

from .contract import TasteInput
from .identity import CARD


async def _run(**kwargs) -> dict:
    from .agent import TasteAgent

    return await TasteAgent()(kwargs)


tool = StructuredTool.from_function(
    coroutine=_run,
    name=CARD["name"],
    description=describe(CARD),
    args_schema=TasteInput,
)
