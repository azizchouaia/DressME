import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from modules.m07_local_catalogue.agent import LocalShopAgent
from modules.m07_local_catalogue.contract import LocalShopInput

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "input.json").read_text())


def test_input_fixture_matches_contract():
    LocalShopInput.model_validate(FIXTURE)


def test_input_needs_something_to_search():
    with pytest.raises(ValidationError):
        LocalShopInput.model_validate({"city": "Tunis"})
    LocalShopInput.model_validate({"gap": "white shirt"})
    LocalShopInput.model_validate({"subcategory": "sneakers", "max_price_tnd": 80})


def test_agent_metadata():
    agent = LocalShopAgent()
    assert agent.name == "localshop"
    assert agent.description
    assert agent.catalogue is None  # nothing heavy is loaded at import / construction time
