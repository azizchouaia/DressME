"""Donation suggestions (donation.py + POST /items/{id}/donation-suggestions). The LLM is a scripted fake."""

import json

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from modules.m01_wardrobe import donation
from modules.m01_wardrobe.router import router

DEMO = "usr_demo"


class Scripted(BaseChatModel):
    answer: str = ""
    error: str | None = None
    prompts: list = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.prompts.append(messages[-1].content)
        if self.error:
            raise httpx.ConnectError(self.error)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(self.answer))])


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    yield TestClient(app)
    donation.set_model(None)


def first_item(client) -> dict:
    return client.post("/m01/items", json={"user_id": DEMO}).json()["items"][0]


def suggest(client, item_id, city="Sfax"):
    return client.post(f"/m01/items/{item_id}/donation-suggestions?user_id={DEMO}", json={"city": city})


def test_llm_picks_and_explains_but_links_come_from_the_file(client):
    item = first_item(client)
    answer = {
        "suggestions": [
            {"place_id": "neighbourhood", "reason": "Une pièce du quotidien, parfaite pour la collecte de l'Aïd."},
            {"place_id": "made_up_place", "reason": "inventé"},
            {"place_id": "crt", "reason": "Le comité de Sfax la donnera à une famille."},
        ],
        "message": "Ta pièce va faire plaisir !",
    }
    model = Scripted(answer=json.dumps(answer), prompts=[])
    donation.set_model(model)
    r = suggest(client, item["item_id"])
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["llm_used"] is True and out["message"] == "Ta pièce va faire plaisir !"
    # unknown id dropped, then completed up to max_suggestions with the list's order and text
    assert [s["place_id"] for s in out["suggestions"]] == ["neighbourhood", "crt", "municipality"]
    assert out["suggestions"][2]["reason"].startswith("vêtements chauds, manteaux")
    crt = out["suggestions"][1]
    assert crt["url"] == "https://www.croissant-rouge.tn" and crt["place"] == "association"
    assert crt["reason"].startswith("Le comité de Sfax")
    prompt = model.prompts[0]
    assert "USER'S CITY: Sfax" in prompt and "id=crt" in prompt and item["category"] in prompt


@pytest.mark.parametrize("model", [Scripted(answer="not json", prompts=[]), Scripted(error="refused", prompts=[])])
def test_without_a_usable_llm_the_list_is_shown(client, model):
    donation.set_model(model)
    out = suggest(client, first_item(client)["item_id"]).json()
    assert out["llm_used"] is False and out["model"] is None
    assert [s["place_id"] for s in out["suggestions"]] == ["crt", "neighbourhood", "municipality"]
    assert out["suggestions"][0]["reason"].startswith("vêtements chauds")


def test_retrieval_filters_city_and_category(client, monkeypatch):
    places = {
        "places": [
            {"id": "sfax_shoes", "name": "A", "type": "association", "cities": ["Sfax"], "accepts": ["shoes"],
             "how": "h", "best_for": "b"},
            {"id": "everywhere", "name": "B", "type": "personal", "cities": ["*"], "accepts": ["*"],
             "how": "h", "best_for": "b"},
        ]
    }
    monkeypatch.setattr(donation, "load_places", lambda: places)
    items = client.post("/m01/items", json={"user_id": DEMO}).json()["items"]
    shoes = next(i for i in items if i["category"] == "shoes")
    top = next(i for i in items if i["category"] == "top")
    from modules.m01_wardrobe.contract import WardrobeItem

    ids = lambda item, city: [p["id"] for p in donation.retrieve(WardrobeItem.model_validate(item), city)]  # noqa: E731
    assert ids(shoes, "Sfax") == ["sfax_shoes", "everywhere"]
    assert ids(shoes, "Tunis") == ["everywhere"]
    assert ids(top, "Sfax") == ["everywhere"]


def test_unknown_item_is_404(client):
    assert suggest(client, "itm_nope").status_code == 404


def test_every_place_in_the_file_is_well_formed():
    data = donation.load_places()
    for p in data["places"]:
        assert p["type"] in donation.PLACE_OF_TYPE
        assert p["url"] is None or (p["url"].startswith("https://") and p["verified_on"])  # a link is verified
