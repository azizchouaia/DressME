"""Exposes M10 to the orchestrator (picked up automatically by orchestrator/registry.py)."""

from langchain_core.tools import StructuredTool

from shared.agent_card import describe

from .contract import ShareCardInput
from .identity import CARD


async def _run(**kwargs) -> dict:
    from .singleton import share_agent  # lazy: Pillow & co. are only needed when the tool is called

    return await share_agent(kwargs)


tool = StructuredTool.from_function(
    coroutine=_run,
    name=CARD["name"],
    description=describe(CARD),
    args_schema=ShareCardInput,
)
