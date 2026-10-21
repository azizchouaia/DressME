"""Exposes M15 to the orchestrator (picked up automatically by orchestrator/registry.py)."""

from langchain_core.tools import StructuredTool

from shared.agent_card import describe

from .contract import ChallengesInput
from .identity import CARD


async def _run(**kwargs) -> dict:
    from .singleton import challenges_agent  # lazy import

    return await challenges_agent(kwargs)


tool = StructuredTool.from_function(
    coroutine=_run,
    name=CARD["name"],
    description=describe(CARD),
    args_schema=ChallengesInput,
)
