"""Exposes M10 to the orchestrator (picked up automatically by orchestrator/registry.py)."""

from langchain_core.tools import StructuredTool

from .contract import ShareCardInput


async def _run(**kwargs) -> dict:
    from .singleton import share_agent  # lazy: Pillow & co. are only needed when the tool is called

    return await share_agent(kwargs)


tool = StructuredTool.from_function(
    coroutine=_run,
    name="share",
    description=(
        "Create a shareable image card (outfit, board, try-on, recap, give-away, challenge, trip, poll) "
        "with a referral link, and track how many new users the sharing brings."
    ),
    args_schema=ShareCardInput,
)
