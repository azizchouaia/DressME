from pathlib import Path

import yaml

from shared.base_agent import BaseAgent

from .contract import ProfileInput, ProfileOutput
from .pipeline import style_vector, bandit, analytics, cold_start  # noqa: F401

CONFIG = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text())


class ProfileAgent(BaseAgent[ProfileInput, ProfileOutput]):
    name = "profile"
    description = "Learn the user's style from feedback events and compute wardrobe analytics (wear rate, duplicates, gaps)."
    input_model = ProfileInput
    output_model = ProfileOutput
    is_async_job = False

    def __init__(self, config: dict | None = None):
        super().__init__(config or CONFIG)

    async def setup(self) -> None:
        # Load models once here (weights from ml/models via DVC).
        pass

    async def run(self, inp: ProfileInput) -> ProfileOutput:
        # TODO: style_vector.run(...)
        # TODO: bandit.run(...)
        # TODO: analytics.run(...)
        # TODO: cold_start.run(...)
        raise NotImplementedError("ProfileAgent.run — implement the pipeline")
