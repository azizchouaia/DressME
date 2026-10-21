"""One shape of identity card for every DressMe agent.

The orchestrator reads the card to choose an agent. A module that is only a
skill names the agent that owns it and does not ship a tool.py.
"""

from typing import Literal

from pydantic import BaseModel, Field

from shared.base_agent import BaseAgent


class AgentCall(BaseModel):
    """Arguments the orchestrator sends to an agent that is still on its mock."""

    user_id: str
    session_id: str = "default"
    language: Literal["en", "fr", "ar"] = "en"
    message: str = ""
    payload: dict = Field(default_factory=dict)


class AgentResult(BaseModel):
    agent: str
    result: dict = Field(default_factory=dict)
    question: str | None = None
    next_actions: list[dict] = Field(default_factory=list)
    mocked: bool = False


def describe(card: dict) -> str:
    """Tool text built from the card, so the planner and the card cannot drift apart."""

    skills = ", ".join(f"{key}: {value}" for key, value in card.get("skills", {}).items())
    use = "; ".join(card.get("when_to_use") or [])
    avoid = "; ".join(card.get("when_not_to_use") or [])
    return (
        f"{card['name']} ({card['module']}, {card['owner']}): {card['role']} "
        f"Skills: {skills}. Use when: {use}. Do not use when: {avoid}."
    )


def build_mock_agent(card: dict, call):
    """An agent entry whose decision is still the module mock. The card is already final."""

    class GeneratedAgent(BaseAgent[AgentCall, AgentResult]):
        name = card["name"]
        description = describe(card)
        input_model = AgentCall
        output_model = AgentResult

        async def run(self, inp: AgentCall) -> AgentResult:
            raw = call(inp)
            body = raw.get("result", raw) if isinstance(raw, dict) else {"value": raw}
            return AgentResult(
                agent=card["name"],
                result=body if isinstance(body, dict) else {"value": body},
                next_actions=list(card.get("handoff") or []),
                mocked=bool(raw.get("mocked")) if isinstance(raw, dict) else False,
            )

    GeneratedAgent.__name__ = f"{card['name'].title()}Agent"
    return GeneratedAgent
