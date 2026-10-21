"""Real implementation of M10 (same signature as mock.py). The logic lives in agent.py + pipeline/."""

from .singleton import share_agent


async def card(req: dict) -> dict:
    """`req` = CardRequest as a dict; `payload` = a ShareCardInput."""
    payload = {"user_id": req.get("user_id") or "anonymous", **(req.get("payload") or {})}
    return {"result": await share_agent(payload), "mocked": False}
