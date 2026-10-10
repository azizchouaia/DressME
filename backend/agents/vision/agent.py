from pathlib import Path

import yaml

from shared.base_agent import BaseAgent

from .contract import VisionInput, VisionOutput
from .pipeline import segment, classify, colors, embed  # noqa: F401

CONFIG = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text())


class VisionAgent(BaseAgent[VisionInput, VisionOutput]):
    name = "vision"
    description = "Digitise a garment photo: remove background, classify type/colour/season, compute an embedding."
    input_model = VisionInput
    output_model = VisionOutput
    is_async_job = True

    def __init__(self, config: dict | None = None):
        super().__init__(config or CONFIG)

    async def setup(self) -> None:
        # Load models once here (weights from ml/models via DVC).
        pass

    async def run(self, inp: VisionInput) -> VisionOutput:
        # TODO: segment.run(...)
        # TODO: classify.run(...)
        # TODO: colors.run(...)
        # TODO: embed.run(...)
        raise NotImplementedError("VisionAgent.run — implement the pipeline")
