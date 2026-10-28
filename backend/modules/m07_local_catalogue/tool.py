"""Exposes the BO6 agent (M7) to the orchestrator (BO8) as a tool; picked up automatically by the registry.

The card (identity.py) is the description.
"""

from langchain_core.tools import StructuredTool

from . import service
from .contract import LocalShopInput
from .identity import CARD, tool_description


async def _run(**kwargs) -> dict:
    # same agent as the API (FashionCLIP is loaded once); logged as coming from the assistant
    return await service.search(kwargs, channel="orchestrator")


tool = StructuredTool.from_function(
    coroutine=_run,
    name=CARD["name"],
    description=tool_description(),
    args_schema=LocalShopInput,
)
