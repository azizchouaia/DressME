"""Real implementation of M15 (same signature as mock.py). The logic lives in agent.py + pipeline/."""

from .singleton import challenges_agent


async def challenges(req: dict) -> dict:
    """`req` = ChallengesRequest as a dict; `payload` = a ChallengesInput (action + fields)."""
    payload = {"user_id": req.get("user_id") or "anonymous", **(req.get("payload") or {})}
    return {"result": await challenges_agent(payload), "mocked": False}
