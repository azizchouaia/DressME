"""Exposes the agent to the orchestrator as a LangGraph/LangChain tool."""

from langchain_core.tools import StructuredTool

from .agent import VisionAgent
from .contract import VisionInput

_agent = VisionAgent()


async def _run(**kwargs) -> dict:
    return await _agent(kwargs)


tool = StructuredTool.from_function(
    coroutine=_run,
    name=_agent.name,
    description=_agent.description,
    args_schema=VisionInput,
)
