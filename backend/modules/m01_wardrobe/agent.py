"""Wardrobe agent. The decision is Amine's M1 service, not the week-1 mock."""

from shared.agent_card import AgentCall, AgentResult, describe
from shared.base_agent import BaseAgent

from .identity import CARD


class WardrobeAgent(BaseAgent[AgentCall, AgentResult]):
    name = CARD["name"]
    description = describe(CARD)
    input_model = AgentCall
    output_model = AgentResult

    async def run(self, inp: AgentCall) -> AgentResult:
        from shared.config import settings

        from . import mock, service
        from .config import use_mocks
        from .contract import ClassifyRequest, ItemsRequest

        image = inp.payload.get("image") or inp.payload.get("image_base64")

        async def ask(impl):
            if image:
                return await impl.classify(ClassifyRequest(user_id=inp.user_id, image=str(image)))
            return await impl.items(ItemsRequest(user_id=inp.user_id))

        impl = mock if use_mocks(settings.use_mocks) else service
        try:
            found = await ask(impl)
        except (OSError, ConnectionError):  # database / storage down -> the mock keeps the chat alive
            found = await ask(mock)
        data = found.model_dump(mode="json")
        return AgentResult(
            agent=CARD["name"],
            result=data,
            next_actions=list(CARD["handoff"]),
            mocked=bool(data.get("mocked")),
        )


Agent = WardrobeAgent
