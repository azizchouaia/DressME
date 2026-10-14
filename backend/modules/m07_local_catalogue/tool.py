"""Exposes M7 to the orchestrator (M8 / BO8) as a tool; picked up automatically by the registry."""

from langchain_core.tools import StructuredTool

from . import service
from .agent import LocalShopAgent
from .contract import LocalShopInput


async def _run(**kwargs) -> dict:
    return await service.search(kwargs)  # same agent as the API: FashionCLIP is loaded once


tool = StructuredTool.from_function(
    coroutine=_run,
    name=LocalShopAgent.name,
    description=LocalShopAgent.description,
    args_schema=LocalShopInput,
)
