from pathlib import Path

import yaml

from shared.base_agent import BaseAgent

from .contract import LocalShopInput, LocalShopOutput
from .pipeline import retrieve, filter, rerank, ingest  # noqa: F401

CONFIG = yaml.safe_load((Path(__file__).parent / "config.yaml").read_text())


class LocalShopAgent(BaseAgent[LocalShopInput, LocalShopOutput]):
    name = "localshop"
    description = "Find matching pieces in Tunisian boutiques and brands from the curated shop knowledge base."
    input_model = LocalShopInput
    output_model = LocalShopOutput
    is_async_job = False

    def __init__(self, config: dict | None = None):
        super().__init__(config or CONFIG)

    async def setup(self) -> None:
        # Load models once here (weights from ml/models via DVC).
        pass

    async def run(self, inp: LocalShopInput) -> LocalShopOutput:
        # TODO: retrieve.run(...)
        # TODO: filter.run(...)
        # TODO: rerank.run(...)
        # TODO: ingest.run(...)
        raise NotImplementedError("LocalShopAgent.run — implement the pipeline")
