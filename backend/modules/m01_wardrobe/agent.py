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
        from . import service
        from .contract import ClassifyRequest, ItemsRequest

        image = inp.payload.get("image") or inp.payload.get("image_base64")
        if image:
            found = await service.classify(ClassifyRequest(user_id=inp.user_id, image=str(image)))
        else:
            found = await service.items(ItemsRequest(user_id=inp.user_id))
        data = found.model_dump(mode="json")
        return AgentResult(
            agent=CARD["name"],
            result=data,
            next_actions=list(CARD["handoff"]),
            mocked=bool(data.get("mocked")),
        )


Agent = WardrobeAgent
