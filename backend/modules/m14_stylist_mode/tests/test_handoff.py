"""F7 hand-off: escalate? -> which stylist -> summary -> queue -> accept / decline / close."""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m14_stylist_mode import router as m14_router
from modules.m14_stylist_mode.handoff import escalate
from modules.m14_stylist_mode.paths import CONFIG
from modules.m14_stylist_mode.simulate import pros


@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(m14_router.router)
    asyncio.run(pros.seed())
    return TestClient(app)


def user(*texts):
    return [{"role": "user", "text": t} for t in texts]


@pytest.mark.parametrize(
    ("texts", "reason"),
    [
        (["je veux parler à une styliste"], "asks_human"),
        (["can I talk to a real person?"], "asks_human"),
        (["n7eb nahki m3a bnadem"], "asks_human"),
        (["ça marche pas, tu comprends rien", "une tenue pour le mariage de ma soeur"], "frustration"),
    ],
)
def test_escalates(texts, reason):
    out = escalate.run(user(*texts), None, CONFIG)
    assert out["escalate"] and out["reason"] == reason


def test_does_not_escalate_a_simple_request():
    out = escalate.run(user("baskets blanches max 80 dt"), 0.9, CONFIG)
    assert not out["escalate"] and out["signals"] == {}


def test_occasion_alone_is_not_enough_but_with_low_confidence_it_is():
    assert not escalate.run(user("une robe pour un mariage"), None, CONFIG)["escalate"]
    assert escalate.run(user("une robe pour un mariage"), 0.3, CONFIG)["escalate"]  # 1-(0.65 x 0.6) = 0.61


def test_handoff_picks_the_wedding_stylist_in_sousse_and_writes_the_summary(api):
    body = {
        "user_id": "usr_042",
        "session_id": "chat_1",
        "messages": user(
            "une tenue pour le mariage de ma soeur à Sousse, budget 300 dt",
            "je préfère parler à une styliste",
        ),
    }
    h = api.post("/m14/handoff", json=body).json()
    assert h["status"] == "queued" and h["escalation"]["reason"] == "asks_human"
    assert h["candidates"][0]["name"] == "Ines (demo)"  # Sousse + mariage + speaks fr
    assert h["pro_id"] == h["candidates"][0]["pro_id"]
    assert (h["occasion"], h["budget_tnd"], h["city"]) == ("mariage", 300, "Sousse")
    assert h["summary"][0].startswith("Request: une tenue pour le mariage")
    assert "Occasion: wedding · budget: 300 TND · city: Sousse" in h["summary"]
    assert "Why a human: asked to talk to a stylist" in h["summary"]
    assert len(h["summary"]) <= 5


def test_queue_accept_decline_close(api):
    body = {"user_id": "usr_043", "session_id": "c2", "messages": user("styliste svp, costume homme mariage")}
    h = api.post("/m14/handoff", json=body).json()
    first, second = h["candidates"][0]["pro_id"], h["candidates"][1]["pro_id"]
    assert [x["handoff_id"] for x in api.get("/m14/handoff/queue", params={"pro_id": first}).json()] == [
        h["handoff_id"]
    ]
    assert (
        api.patch(
            f"/m14/handoff/{h['handoff_id']}", json={"pro_id": second, "status": "accepted"}
        ).status_code
        == 403
    )
    h = api.patch(f"/m14/handoff/{h['handoff_id']}", json={"pro_id": first, "status": "declined"}).json()
    assert h["status"] == "queued" and h["pro_id"] == second  # goes to the next stylist
    h = api.patch(f"/m14/handoff/{h['handoff_id']}", json={"pro_id": second, "status": "accepted"}).json()
    assert h["status"] == "accepted"
    assert (
        api.patch(
            f"/m14/handoff/{h['handoff_id']}", json={"pro_id": second, "status": "declined"}
        ).status_code
        == 422
    )
    h = api.patch(f"/m14/handoff/{h['handoff_id']}", json={"pro_id": second, "status": "closed"}).json()
    assert h["status"] == "closed" and [e["status"] for e in h["history"]] == [
        "queued",
        "declined",
        "queued",
        "accepted",
        "closed",
    ]


def test_not_needed_is_not_queued_and_force_always_is(api):
    body = {"user_id": "usr_044", "session_id": "c3", "messages": user("baskets blanches")}
    h = api.post("/m14/handoff", json=body).json()
    assert h["status"] == "not_needed" and h["candidates"] == []
    assert api.get(f"/m14/handoff/{h['handoff_id']}").status_code == 404  # nothing stored
    h = api.post("/m14/handoff", json=body | {"force": True}).json()
    assert h["status"] == "queued" and h["escalation"]["reason"] == "user_choice"


def test_check_only(api):
    out = api.post(
        "/m14/handoff/check", json={"user_id": "u", "messages": user("nul, n'importe quoi")}
    ).json()
    assert out["reason"] == "frustration" and not out["escalate"]  # 0.5 < 0.6


def test_one_open_request_per_client_and_accepting_opens_the_client_file(api):
    body = {
        "user_id": "usr_090",
        "session_id": "c9",
        "messages": user("je veux une styliste pour un mariage"),
    }
    first = api.post("/m14/handoff", json=body).json()
    again = api.post("/m14/handoff", json=body).json()  # tapped twice
    assert again["handoff_id"] == first["handoff_id"] and again["already_open"]
    assert first["messages"][0]["text"] == "je veux une styliste pour un mariage"

    pro = first["pro_id"]
    assert api.get("/m14/clients/usr_090/wardrobe", params={"pro_id": pro}).status_code == 403
    api.patch(f"/m14/handoff/{first['handoff_id']}", json={"pro_id": pro, "status": "accepted"})
    wardrobe = api.get("/m14/clients/usr_090/wardrobe", params={"pro_id": pro}).json()
    assert len(wardrobe["items"]) == 8 and wardrobe["sources"]["m1"] == "mock"
    assert api.get("/m14/clients/usr_090/brief", params={"pro_id": pro}).status_code == 200
    link = api.get("/m14/clients", params={"pro_id": pro, "client_id": "usr_090"}).json()[0]
    assert link["status"] == "active" and "hand-off" in link["message"]

    api.patch(f"/m14/handoff/{first['handoff_id']}", json={"pro_id": pro, "status": "closed"})
    new = api.post("/m14/handoff", json=body).json()  # closed: a new request is a new one
    assert new["handoff_id"] != first["handoff_id"] and not new["already_open"]


def test_the_main_occasion_wins_in_a_message():
    from modules.m14_stylist_mode.handoff.summary import facts

    said = facts(user("une robe de soirée pour un mariage à Tunis, max 200 dt"))
    assert (said["occasion"], said["budget_tnd"], said["city"]) == ("mariage", 200, "Tunis")
    assert facts(user("une robe pour un mariage", "finalement c'est pour une soirée"))["occasion"] == "soirée"


def test_a_new_message_goes_into_the_open_request(api):
    first = {"user_id": "usr_091", "session_id": "c1", "messages": user("robe rouge"), "force": True}
    h = api.post("/m14/handoff", json=first).json()
    again = {"user_id": "usr_091", "session_id": "c2", "messages": user("je veux jupe noire avec pull blanc")}
    h2 = api.post("/m14/handoff", json=again).json()
    assert h2["handoff_id"] == h["handoff_id"] and h2["already_open"] and h2["pro_id"] == h["pro_id"]
    assert [m["text"] for m in h2["messages"]] == ["robe rouge", "je veux jupe noire avec pull blanc"]
    assert "Last message: je veux jupe noire avec pull blanc" in h2["summary"]
    assert h2["history"][-1]["status"] == "new_message"
