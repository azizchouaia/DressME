"""Exposes M15 to the orchestrator (picked up automatically by orchestrator/registry.py)."""

from langchain_core.tools import StructuredTool

from .contract import ChallengesInput


async def _run(**kwargs) -> dict:
    from .singleton import challenges_agent  # lazy import

    return await challenges_agent(kwargs)


tool = StructuredTool.from_function(
    coroutine=_run,
    name="challenges",
    description=(
        "Community style challenges (e.g. 7 days, 7 outfits): list or recommend, create, join, "
        "log today's outfit (rule check, points, ML chance to finish, coach tip), progress, leaderboard."
    ),
    args_schema=ChallengesInput,
)
