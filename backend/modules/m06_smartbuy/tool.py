"""Exposes the agent to the orchestrator as a tool. The card is the description."""

from langchain_core.tools import StructuredTool

from shared.agent_card import describe

from .contract import SmartBuyInput
from .identity import CARD

_agent = None


def agent():
    global _agent
    if _agent is None:
        from .agent import SmartBuyAgent

        _agent = SmartBuyAgent()
    return _agent


async def _run(**kwargs) -> dict:
    return await agent()(kwargs)


tool = StructuredTool.from_function(
    coroutine=_run, name=CARD["name"], description=describe(CARD), args_schema=SmartBuyInput
)
