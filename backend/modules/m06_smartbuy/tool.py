"""Exposes Smart Buy to the orchestrator (BO8) as a tool. The card (identity.py) is the description."""

from langchain_core.tools import StructuredTool

from .contract import SmartBuyInput
from .identity import CARD, tool_description

_agent = None


def agent():
    global _agent
    if _agent is None:
        from .agent import SmartBuyAgent

        _agent = SmartBuyAgent()
    return _agent


async def _run(**kwargs) -> dict:
    return await agent()(kwargs)


tool = StructuredTool.from_function(coroutine=_run, name=CARD["name"], description=tool_description(),
                                    args_schema=SmartBuyInput)
