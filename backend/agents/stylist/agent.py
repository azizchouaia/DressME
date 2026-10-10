from pathlib import Path

import yaml

from shared.base_agent import BaseAgent

from .contract import StylistInput, StylistOutput
from .pipeline import candidates, compatibility, diversify, explain  # noqa: F401

CONFIG = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text())


class StylistAgent(BaseAgent[StylistInput, StylistOutput]):
    name = "stylist"
    description = "Generate ranked outfits from the user's wardrobe for an occasion, the weather and their style."
    input_model = StylistInput
    output_model = StylistOutput
    is_async_job = False

    def __init__(self, config: dict | None = None):
        super().__init__(config or CONFIG)

    async def setup(self) -> None:
        # Load models once here (weights from ml/models via DVC).
        pass

    async def run(self, inp: StylistInput) -> StylistOutput:
        # TODO: candidates.run(...)
        # TODO: compatibility.run(...)
        # TODO: diversify.run(...)
        # TODO: explain.run(...)
        raise NotImplementedError("StylistAgent.run — implement the pipeline")
