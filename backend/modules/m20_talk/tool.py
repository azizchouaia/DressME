"""Exposes the talk agent to the orchestrator. The card is the description."""

from langchain_core.tools import StructuredTool

from shared.agent_card import describe

from .contract import TalkInput
from .identity import CARD


async def _run(**kwargs) -> dict:
    from .agent import TalkAgent

    return await TalkAgent()(kwargs)


tool = StructuredTool.from_function(
    coroutine=_run,
    name=CARD["name"],
    description=describe(CARD),
    args_schema=TalkInput,
)
