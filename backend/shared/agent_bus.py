"""How agents find and talk to each other: every module that ships an `agent.py` with an `agent` object is
on the bus. Another BO's agent asks ours with

    from shared.agent_bus import ask
    res = await ask("m02_recommendation", "recommend", {"context": {"occasion": "work"}}, user_id="u1",
                    sender="m06_smartbuy")

In-process today; the same message works over HTTP (POST /agents/{name}) when agents run in separate services.
"""

from __future__ import annotations

import importlib
import pkgutil
from functools import lru_cache

import modules


@lru_cache(maxsize=1)
def agents() -> dict:
    out = {}
    for m in sorted(pkgutil.iter_modules(modules.__path__), key=lambda m: m.name):
        try:
            mod = importlib.import_module(f"modules.{m.name}.agent")
        except ModuleNotFoundError as e:
            if e.name != f"modules.{m.name}.agent":
                raise
            continue
        a = getattr(mod, "agent", None)
        if a is not None:
            out[a.name] = a
    # BO idea agents + BO orchestrators: bo/<bo>/agents.py exposes AGENTS (instances)
    import bo

    for m in sorted(pkgutil.iter_modules(bo.__path__), key=lambda m: m.name):
        try:
            mod = importlib.import_module(f"bo.{m.name}.agents")
        except ModuleNotFoundError as e:
            if e.name != f"bo.{m.name}.agents":
                raise
            continue
        for a in getattr(mod, "AGENTS", []):
            out[a.name] = a
    return out


def get(name: str):
    a = agents().get(name)
    if a is None:
        raise KeyError(f"no agent {name!r}; available: {', '.join(sorted(agents()))}")
    return a


async def ask(
    name: str, action: str, payload: dict | None = None, user_id: str | None = None, sender: str | None = None
) -> dict:
    return await get(name)({"action": action, "payload": payload or {}, "user_id": user_id, "sender": sender})


def directory() -> list[dict]:
    """Cards of every agent: what each one can do (for other agents and the orchestrator)."""
    return [a.card() if hasattr(a, "card") else {"agent": a.name, "description": a.description}
            for a in agents().values()]
