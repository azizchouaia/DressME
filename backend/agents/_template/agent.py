from shared.base_agent import BaseAgent

from .contract import TemplateInput, TemplateOutput


class TemplateAgent(BaseAgent[TemplateInput, TemplateOutput]):
    name = "template"
    description = "Describe in one sentence what this agent does (the orchestrator reads it)."
    input_model = TemplateInput
    output_model = TemplateOutput

    async def run(self, inp: TemplateInput) -> TemplateOutput:
        return TemplateOutput(result=f"hello {inp.user_id}")
