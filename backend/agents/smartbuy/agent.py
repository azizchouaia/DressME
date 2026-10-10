from pathlib import Path

import yaml

from shared.base_agent import BaseAgent

from .contract import SmartBuyInput, SmartBuyOutput
from .pipeline import neighbours, redundancy, unlock, score  # noqa: F401

CONFIG = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text())


class SmartBuyAgent(BaseAgent[SmartBuyInput, SmartBuyOutput]):
    name = "smartbuy"
    description = "Judge whether a new piece complements or duplicates the user's wardrobe and how many outfits it unlocks."
    input_model = SmartBuyInput
    output_model = SmartBuyOutput
    is_async_job = False

    def __init__(self, config: dict | None = None):
        super().__init__(config or CONFIG)

    async def setup(self) -> None:
        # Load models once here (weights from ml/models via DVC).
        pass

    async def run(self, inp: SmartBuyInput) -> SmartBuyOutput:
        # TODO: neighbours.run(...)
        # TODO: redundancy.run(...)
        # TODO: unlock.run(...)
        # TODO: score.run(...)
        raise NotImplementedError("SmartBuyAgent.run — implement the pipeline")
