"""Module agents: one agent per module, built on BaseAgent, all speaking the same message.

A message to an agent (from the orchestrator, another BO's agent, or HTTP):
    {"action": "recommend", "user_id": "u1", "payload": {...}, "sender": "m06_smartbuy"}
The answer:
    {"agent": "m02_recommendation", "action": "recommend", "ok": true, "result": {...}, "mocked": false,
     "error": null}

`payload` is exactly the payload of the module's HTTP endpoint for that action (its contract.py), so an agent
call and an HTTP call give the same result. Each agent publishes a card (name, description, actions + what
each action needs) so other agents / the orchestrator know what to ask.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, ClassVar

from pydantic import BaseModel

from .base_agent import BaseAgent


class AgentRequest(BaseModel):
    action: str
    user_id: str | None = None
    payload: dict[str, Any] = {}
    sender: str | None = None  # who is asking (another agent's name, "orchestrator", "http")


class AgentResponse(BaseModel):
    agent: str
    action: str
    ok: bool
    result: dict[str, Any] = {}
    mocked: bool = False
    error: str | None = None


@dataclass
class Action:
    """One thing the agent can do. `call(req)` gets the validated team envelope {user_id, payload}."""

    description: str
    call: Callable[[dict], dict]
    request_model: type[BaseModel] | None = None  # the endpoint's request model (validates + fills defaults)

    def payload_fields(self) -> dict[str, str]:
        if self.request_model is None:
            return {}
        payload = self.request_model.model_fields.get("payload")
        model = payload.annotation if payload is not None else None
        if not isinstance(model, type) or not issubclass(model, BaseModel):
            return {}
        return {k: str(f.annotation).replace("typing.", "") for k, f in model.model_fields.items()}


class ActionAgent(BaseAgent[AgentRequest, AgentResponse]):
    """BaseAgent whose input names an action. Subclasses fill `name`, `description` and `actions()`."""

    input_model: ClassVar[type[BaseModel]] = AgentRequest
    output_model: ClassVar[type[BaseModel]] = AgentResponse
    depends_on: ClassVar[tuple[str, ...]] = ()  # agents this one asks

    def actions(self) -> dict[str, Action]:
        raise NotImplementedError

    async def run(self, inp: AgentRequest) -> AgentResponse:
        acts = self.actions()
        act = acts.get(inp.action)
        if act is None:
            return AgentResponse(
                agent=self.name,
                action=inp.action,
                ok=False,
                error=f"unknown action; available: {', '.join(sorted(acts))}",
            )
        req = {"user_id": inp.user_id, "payload": inp.payload}
        try:
            if act.request_model is not None:
                req = act.request_model.model_validate(req).model_dump()
            out = await asyncio.to_thread(act.call, req)  # services are sync (models, DB): off the event loop
        except Exception as e:  # noqa: BLE001  - an agent answers, it never crashes the caller
            return AgentResponse(
                agent=self.name, action=inp.action, ok=False, error=f"{type(e).__name__}: {e}"
            )
        out = out if isinstance(out, dict) else {"result": out}
        result = out.get("result", out)
        return AgentResponse(
            agent=self.name,
            action=inp.action,
            ok=True,
            result=result if isinstance(result, dict) else {"value": result},
            mocked=bool(out.get("mocked", False)),
        )

    def card(self) -> dict:
        return {
            "agent": self.name,
            "description": self.description,
            "depends_on": list(self.depends_on),
            "actions": {
                k: {"description": a.description, "payload": a.payload_fields()}
                for k, a in self.actions().items()
            },
        }

    def health(self) -> dict:
        return {"agent": self.name, "status": "ok", "actions": sorted(self.actions())}


def langchain_tool(agent: ActionAgent):
    """The agent as a LangChain tool for the orchestrator (modules/<m>/tool.py exposes it as `tool`)."""
    from langchain_core.tools import StructuredTool
    from pydantic import Field, create_model

    acts = agent.actions()
    args = create_model(
        f"{agent.name}_args",
        action=(
            str,
            Field(description="one of: " + "; ".join(f"{k} = {a.description}" for k, a in acts.items())),
        ),
        payload=(
            dict,
            Field(default_factory=dict, description="the action's payload (see the module contract)"),
        ),
        user_id=(str | None, Field(default=None)),
    )

    async def _run(action: str, payload: dict | None = None, user_id: str | None = None) -> dict:
        return await agent(
            {"action": action, "payload": payload or {}, "user_id": user_id, "sender": "orchestrator"}
        )

    return StructuredTool.from_function(
        coroutine=_run, name=agent.name, description=agent.description, args_schema=args
    )
