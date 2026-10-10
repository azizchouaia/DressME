from pathlib import Path

import yaml

from shared.base_agent import BaseAgent

from .contract import TryOnInput, TryOnOutput
from .pipeline import body, garments, render, fallback_2d  # noqa: F401

CONFIG = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text())


class TryOnAgent(BaseAgent[TryOnInput, TryOnOutput]):
    name = "tryon"
    description = "Render an outfit on the user's faceless 3D avatar built from body measurements."
    input_model = TryOnInput
    output_model = TryOnOutput
    is_async_job = True

    def __init__(self, config: dict | None = None):
        super().__init__(config or CONFIG)

    async def setup(self) -> None:
        # Load models once here (weights from ml/models via DVC).
        pass

    async def run(self, inp: TryOnInput) -> TryOnOutput:
        # TODO: body.run(...)
        # TODO: garments.run(...)
        # TODO: render.run(...)
        # TODO: fallback_2d.run(...)
        raise NotImplementedError("TryOnAgent.run — implement the pipeline")
