"""One taste agent for every user. The model is shared. The memory is per person."""

from shared.base_agent import BaseAgent
from shared.taste_agent import advise, learn

from .contract import TasteInput, TasteOutput


class TasteAgent(BaseAgent[TasteInput, TasteOutput]):
    name = "taste"
    description = "Learn what this person likes and rank outfits or purchases from that memory."
    input_model = TasteInput
    output_model = TasteOutput

    async def run(self, inp: TasteInput) -> TasteOutput:
        if inp.kind and inp.id:
            learn(
                inp.user_id,
                inp.id,
                inp.kind,
                vector=inp.vector or None,
                title=inp.title,
                labels=inp.labels,
                fit=inp.fit,
                gender=inp.gender,
            )
        result = advise(inp.user_id, inp.candidates, purpose=inp.purpose or "outfit")
        result["session_id"] = inp.session_id
        return TasteOutput.model_validate(result)
