"""Avatar agent. Code chooses the pose and the clothes. LangGraph only calls this tool."""

from shared.agent_card import describe
from shared.base_agent import BaseAgent

from .contract import NextAction, TryOnInput, TryOnOutput
from .identity import CARD
from .memory import recall, remember

POSES = {
    "tpose": "tpose",
    "t-pose": "tpose",
    "standing": "stand",
    "stand": "stand",
    "hips": "hips",
    "step": "step",
    "wave": "wave",
}
GARMENTS = {"shirt": "shirt", "shorts": "shorts", "vest": "vest", "tee": "shirt", "top": "shirt"}
UNKNOWN = ("dress", "skirt", "coat", "hat", "jeans", "sneakers")


class TryOnAgent(BaseAgent[TryOnInput, TryOnOutput]):
    name = CARD["name"]
    description = describe(CARD)
    input_model = TryOnInput
    output_model = TryOnOutput

    async def run(self, inp: TryOnInput) -> TryOnOutput:
        from . import service

        previous = recall(inp.user_id, inp.session_id)
        text = " ".join(part for part in (inp.answer, inp.message, inp.pose, " ".join(inp.garments)) if part).lower()
        asked = [word for word in UNKNOWN if word in text]
        if asked:
            question = "I can show the shirt, the shorts, and the vest. Which of these should I put on?"
            decision = remember(inp.user_id, inp.session_id, previous["pose"], previous["garments"], question)
            return TryOnOutput(
                body=service.render({})["result"]["body"],
                pose=previous["pose"],
                garments=previous["garments"],
                question=question,
                decision_id=decision,
            )
        chosen = [GARMENTS[word] for word in GARMENTS if word in text]
        pose = next((POSES[word] for word in POSES if word in text), previous["pose"])
        garments = list(dict.fromkeys(chosen)) or previous["garments"]
        shown = service.render({"user_id": inp.user_id, "payload": {"pose": pose, "garments": garments}})
        decision = remember(inp.user_id, inp.session_id, pose, garments, None)
        return TryOnOutput(
            body=shown["result"]["body"],
            pose=pose,
            garments=garments,
            next_actions=[NextAction.model_validate(item) for item in CARD["handoff"]],
            decision_id=decision,
            mocked=False,
        )


Agent = TryOnAgent
