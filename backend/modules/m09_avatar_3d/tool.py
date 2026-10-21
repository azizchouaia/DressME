"""The plug LangGraph discovers. n8n is not part of this path."""

from langchain_core.tools import StructuredTool

from shared.agent_card import describe

from .agent import TryOnAgent
from .contract import TryOnInput
from .identity import CARD

_agent = TryOnAgent()


async def _run(**kwargs) -> dict:
    return await _agent(kwargs)


tool = StructuredTool.from_function(
    coroutine=_run, name=CARD["name"], description=describe(CARD), args_schema=TryOnInput
)
