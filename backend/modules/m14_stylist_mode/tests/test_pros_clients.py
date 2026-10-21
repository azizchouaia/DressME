"""F1 accounts · F2 consent + brief · F3 review · F4 looks · F5 in-store, through the HTTP API."""

import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m07_local_catalogue import service as m7
from modules.m14_stylist_mode import router as m14_router


@pytest.fixture
def api():
    app = FastAPI()
    app.include_router(m14_router.router)
    return TestClient(app)


def stylist(api, **extra):
    body = {"type": "stylist", "name": "Amel (démo)", "city": "Tunis", "specialities": ["mariage"]} | extra
    return api.post("/m14/pro", json=body).json()


def linked(api, pro_id, client="usr_042", accept=True):
    link = api.post("/m14/clients", json={"pro_id": pro_id, "client_id": client}).json()
    assert link["status"] == "invited"
    return api.post(
        f"/m14/clients/{link['link_id']}/consent", json={"client_id": client, "accept": accept}
    ).json()


# ---- F1
def test_boutique_account_must_be_a_catalogue_shop_once(api):
    ok = api.post("/m14/pro", json={"type": "boutique", "name": "Manuella (démo)", "shop": "Manuella"})
    assert ok.status_code == 200 and ok.json()["verified"] is False
    again = api.post("/m14/pro", json={"type": "boutique", "name": "Autre", "shop": "Manuella"})
    assert again.status_code == 422
    unknown = api.post("/m14/pro", json={"type": "boutique", "name": "X", "shop": "Boutique inconnue"})
    assert unknown.status_code == 422
    assert api.post("/m14/pro", json={"type": "boutique", "name": "Sans boutique"}).status_code == 422


def test_list_and_update_pros(api):
    pro = stylist(api)
    assert [p["pro_id"] for p in api.get("/m14/pro", params={"type": "stylist"}).json()] == [pro["pro_id"]]
    assert api.patch(f"/m14/pro/{pro['pro_id']}", json={"available": False}).json()["available"] is False
    assert api.get("/m14/pro/pro_unknown").status_code == 404


# ---- F2
def test_brief_needs_consent_and_revoke_stops_it(api):
    pro = stylist(api)
    params = {"pro_id": pro["pro_id"]}
    assert api.get("/m14/clients/usr_042/brief", params=params).status_code == 403  # not invited
    link = api.post("/m14/clients", json={"pro_id": pro["pro_id"], "client_id": "usr_042"}).json()
    assert api.get("/m14/clients/usr_042/brief", params=params).status_code == 403  # invited only
    wrong = api.post(f"/m14/clients/{link['link_id']}/consent", json={"client_id": "usr_999", "accept": True})
    assert wrong.status_code == 403  # only the invited client answers
    api.post(f"/m14/clients/{link['link_id']}/consent", json={"client_id": "usr_042", "accept": True})

    brief = api.get("/m14/clients/usr_042/brief", params=params).json()
    assert brief["wardrobe"]["n_items"] == 8 and 1 <= len(brief["summary"]) <= 5
    assert brief["sources"]["m1"] == "mock" and brief["sources"]["m7"] == "real"
    assert "dress red" in brief["wardrobe"]["never_worn"]

    api.delete(f"/m14/clients/{link['link_id']}", params={"client_id": "usr_042"})
    assert api.get("/m14/clients/usr_042/brief", params=params).status_code == 403
    assert api.get("/m14/clients", params={"client_id": "usr_042"}).json()[0]["status"] == "revoked"


def test_brief_shows_the_client_localshop_searches(api):
    asyncio.run(m7.search({"query": "baskets blanches", "user_id": "usr_042", "session_id": "s1"}))
    pro = stylist(api)
    linked(api, pro["pro_id"])
    brief = api.get("/m14/clients/usr_042/brief", params={"pro_id": pro["pro_id"]}).json()
    assert brief["recent_searches"] == ["baskets blanches"]


# ---- F3
def test_review_measures_agreement_with_m5(api):
    pro = stylist(api)
    linked(api, pro["pro_id"])
    same = {
        "archetype": "casual",
        "likes": ["denim", "lin"],
        "dislikes": ["imprimés"],
        "colours": ["white", "navy", "beige"],
    }
    out = api.post("/m14/clients/usr_042/review", json={"pro_id": pro["pro_id"], "corrections": same}).json()
    assert out["changed"] == [] and out["agreement"] == 1.0 and out["sent_to_m5"]
    changed = same | {"archetype": "minimaliste urbain"}
    out = api.post(
        "/m14/clients/usr_042/review", json={"pro_id": pro["pro_id"], "corrections": changed}
    ).json()
    assert out["changed"] == ["archetype"] and out["agreement"] == 0.75
    agreement = api.get("/m14/reviews/agreement").json()
    assert agreement["n_reviews"] == 2 and agreement["overall"] == 0.875
    assert agreement["per_field"]["archetype"] == 0.5 and agreement["per_field"]["likes"] == 1.0


# ---- F4
def test_look_with_local_pieces(api):
    pro = stylist(api)
    linked(api, pro["pro_id"])
    body = {
        "pro_id": pro["pro_id"],
        "client_id": "usr_042",
        "item_ids": ["itm_jean01"],
        "product_ids": ["a1", "a3"],
        "message": "Pour samedi",
    }
    look = api.post("/m14/looks", json=body).json()
    assert [p["shop"] for p in look["products"]] == ["Manuella", "Manuella"]
    assert look["total_price_tnd"] == 164 and 0 < look["score"] <= 1
    assert look["sources"] == {"m2": "mock", "m7": "real", "m10": "mock"}
    assert api.get("/m14/looks", params={"client_id": "usr_042"}).json()[0]["look_id"] == look["look_id"]
    assert api.post("/m14/looks", json=body | {"product_ids": ["nope"]}).status_code == 404
    assert api.post("/m14/looks", json=body | {"client_id": "usr_777"}).status_code == 403


# ---- F5
def test_instore_only_for_the_boutique_own_pieces(api):
    shop = api.post(
        "/m14/pro", json={"type": "boutique", "name": "Manuella (démo)", "shop": "Manuella"}
    ).json()
    linked(api, shop["pro_id"])
    body = {"pro_id": shop["pro_id"], "client_id": "usr_042", "product_id": "a1"}
    out = api.post("/m14/instore/session", json=body).json()
    assert out["product"]["shop"] == "Manuella" and out["verdict"] in ("buy", "think", "skip")
    assert out["sources"]["m6"] == "mock"
    assert api.post("/m14/instore/session", json=body | {"product_id": "b1"}).status_code == 403  # Cravate's
    pro = stylist(api)
    linked(api, pro["pro_id"])
    assert api.post("/m14/instore/session", json=body | {"pro_id": pro["pro_id"]}).status_code == 403


# ---- F2b private conversation
def test_private_conversation_between_the_stylist_and_the_client_only(api):
    amel, sami = stylist(api), stylist(api, name="Sami (démo)")
    link = linked(api, amel["pro_id"])
    chat = f"/m14/chat/{amel['pro_id']}/usr_042"
    assert (
        api.post(
            chat, json={"sender_id": amel["pro_id"], "text": "Bonjour, je regarde ta demande"}
        ).status_code
        == 200
    )
    assert api.post(chat, json={"sender_id": "usr_042", "text": "Merci ! budget 250 dt"}).status_code == 200
    # nobody else: another stylist, another client
    assert api.get(chat, params={"reader_id": sami["pro_id"]}).status_code == 403
    assert api.post(chat, json={"sender_id": "usr_999", "text": "?"}).status_code == 403
    assert (
        api.get(f"/m14/chat/{sami['pro_id']}/usr_042", params={"reader_id": sami["pro_id"]}).status_code
        == 403
    )

    look = {
        "pro_id": amel["pro_id"],
        "client_id": "usr_042",
        "product_ids": ["a3"],
        "message": "Avec ces sandales",
    }
    sent = api.post("/m14/looks", json=look).json()
    talk = api.get(chat, params={"reader_id": "usr_042"}).json()
    assert [(m["role"], m["text"]) for m in talk["messages"]] == [
        ("stylist", "Bonjour, je regarde ta demande"),
        ("client", "Merci ! budget 250 dt"),
        ("stylist", "Avec ces sandales"),
    ]
    assert talk["messages"][-1]["look_id"] == sent["look_id"] and talk["can_write"]

    # the client revokes access: the stylist can no longer read or write, the client still reads
    api.delete(f"/m14/clients/{link['link_id']}", params={"client_id": "usr_042"})
    assert api.get(chat, params={"reader_id": amel["pro_id"]}).status_code == 403
    assert api.post(chat, json={"sender_id": "usr_042", "text": "?"}).status_code == 403
    closed = api.get(chat, params={"reader_id": "usr_042"}).json()
    assert len(closed["messages"]) == 3 and not closed["can_write"]

    # right to be forgotten: only the client deletes it
    assert api.delete(chat, params={"requester_id": amel["pro_id"]}).status_code == 403
    assert api.delete(chat, params={"requester_id": "usr_042"}).status_code == 204
    assert api.get(chat, params={"reader_id": "usr_042"}).json()["messages"] == []
