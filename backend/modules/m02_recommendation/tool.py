from langchain_core.tools import StructuredTool

from shared.agent_card import AgentCall, describe

from .agent import Agent
from .identity import CARD

_agent = Agent()


async def _run(**kwargs) -> dict:
    return await _agent(kwargs)


tool = StructuredTool.from_function(
    coroutine=_run, name=CARD["name"], description=describe(CARD), args_schema=AgentCall
)
