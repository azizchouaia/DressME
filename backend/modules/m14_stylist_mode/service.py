"""Real implementation of M14. Errors the caller can fix raise ValueError (-> 4xx in router.py).

F1 accounts · F2 client links (consent) + brief · F3 review -> M5 · F4 looks · F5 in-store verdict ·
F6 dashboard · F7 hand-off. Other modules are reached through clients.py (real or mock, said in `sources`).
"""

from collections import Counter

from modules.m07_local_catalogue.llm import get_llm

from . import clients, dashboard, mock, store
from .dashboard import insights as dashboard_insights
from .handoff import escalate, match, summary
from .paths import CONFIG


class NotFound(ValueError):
    pass


class Forbidden(ValueError):
    pass


def _pro(pro_id: str) -> dict:
    pro = store.pros.get(pro_id)
    if pro is None:
        raise NotFound(f"unknown pro {pro_id}")
    return pro


# ---------------------------------------------------------------- F1 · accounts
async def create_pro(body: dict) -> dict:
    if body["type"] == "boutique":
        exists, _ = await clients.shop_exists(body["shop"])
        if not exists:
            raise ValueError(f"shop {body['shop']!r} is not in the M7 catalogue (GET /m07/shops)")
        if store.pros.find(type="boutique", shop=body["shop"]):
            raise ValueError(f"shop {body['shop']!r} already has a boutique account")
    pro = {
        **body,
        "pro_id": store.new_id("pro"),
        "verified": False,
        "available": True,
        "created_at": store.now(),
    }
    return store.pros.put(pro["pro_id"], pro)


def get_pro(pro_id: str) -> dict:
    return _pro(pro_id)


def list_pros(type_: str | None = None, city: str | None = None) -> list[dict]:
    pros = store.pros.all().values()
    return [p for p in pros if (not type_ or p["type"] == type_) and (not city or p.get("city") == city)]


def update_pro(pro_id: str, changes: dict) -> dict:
    pro = _pro(pro_id) | {k: v for k, v in changes.items() if v is not None}
    return store.pros.put(pro_id, pro)


# ---------------------------------------------------------------- F2 · client links + consent
def invite(body: dict) -> dict:
    _pro(body["pro_id"])
    for link in store.links.find(pro_id=body["pro_id"], client_id=body["client_id"]):
        if link["status"] in ("invited", "active"):
            return link
    link = {
        **body,
        "link_id": store.new_id("lnk"),
        "status": "invited",
        "created_at": store.now(),
        "answered_at": None,
    }
    return store.links.put(link["link_id"], link)


def consent(link_id: str, client_id: str, accept: bool) -> dict:
    link = store.links.get(link_id)
    if link is None:
        raise NotFound(f"unknown link {link_id}")
    if link["client_id"] != client_id:
        raise Forbidden("only the invited client can answer")
    if link["status"] != "invited":
        raise ValueError(f"link is already {link['status']}")
    link |= {"status": "active" if accept else "declined", "answered_at": store.now()}
    return store.links.put(link_id, link)


def revoke(link_id: str, client_id: str) -> dict:
    link = store.links.get(link_id)
    if link is None:
        raise NotFound(f"unknown link {link_id}")
    if link["client_id"] != client_id:
        raise Forbidden("only the client can revoke access")
    link |= {"status": "revoked", "answered_at": store.now()}
    return store.links.put(link_id, link)


def list_links(pro_id: str | None = None, client_id: str | None = None) -> list[dict]:
    equal = {k: v for k, v in {"pro_id": pro_id, "client_id": client_id}.items() if v}
    return store.links.find(**equal)


def _require_consent(pro_id: str, client_id: str) -> None:
    _pro(pro_id)
    if not store.links.find(pro_id=pro_id, client_id=client_id, status="active"):
        raise Forbidden(f"client {client_id} has not given {pro_id} access (POST /m14/clients + consent)")


async def brief(pro_id: str, client_id: str) -> dict:
    _require_consent(pro_id, client_id)
    items, src_m1 = await clients.wardrobe(client_id)
    worn, src_m3 = await clients.wear_stats(client_id, [i["item_id"] for i in items])
    profile, src_m5 = await clients.style_profile(client_id)
    gaps, _ = await clients.style_gaps(client_id)
    searches, src_m7 = await clients.recent_searches(client_id)

    def name(item: dict) -> str:
        colour = (item.get("colors") or [{}])[0].get("name")
        return " ".join(x for x in (item.get("subcategory") or item["category"], colour) if x)

    wears = {i["item_id"]: worn.get(i["item_id"], i.get("wear_count") or 0) for i in items}
    ranked = sorted(items, key=lambda i: -wears[i["item_id"]])
    prices = [i["price_tnd"] for i in items if i.get("price_tnd")]
    wardrobe = {
        "n_items": len(items),
        "per_category": dict(Counter(i["category"] for i in items).most_common()),
        "top_colours": [
            c
            for c, _ in Counter(
                (i.get("colors") or [{}])[0].get("name") for i in items if i.get("colors")
            ).most_common(3)
        ],
        "most_worn": [name(i) for i in ranked[:3] if wears[i["item_id"]] > 0],
        "never_worn": [name(i) for i in items if wears[i["item_id"]] == 0][:3],
        "price_range_tnd": [min(prices), max(prices)] if prices else None,
    }
    top_cats = ", ".join(f"{c} ({n})" for c, n in list(wardrobe["per_category"].items())[:2])
    likes, dislikes = profile.get("likes") or [], profile.get("dislikes") or []
    taste = " ; ".join(
        t
        for t in (
            f"likes: {', '.join(likes)}" if likes else "",
            f"avoids: {', '.join(dislikes)}" if dislikes else "",
        )
        if t
    )
    lines = [
        f"Style: {profile.get('archetype') or 'unknown'}" + (f" ({taste})." if taste else "."),
        f"Wardrobe: {wardrobe['n_items']} pieces, mostly {top_cats}." if items else "Empty wardrobe.",
    ]
    if wardrobe["most_worn"] or wardrobe["never_worn"]:
        lines.append(
            f"Most worn: {', '.join(wardrobe['most_worn']) or '-'}. "
            f"Never worn: {', '.join(wardrobe['never_worn']) or '-'}."
        )
    if gaps:
        lines.append(f"Missing: {', '.join(gaps)}.")
    if searches:
        lines.append(f"Recently searched: {', '.join(searches[:3])}.")
    return {
        "pro_id": pro_id,
        "client_id": client_id,
        "archetype": profile.get("archetype"),
        "likes": profile.get("likes") or [],
        "dislikes": profile.get("dislikes") or [],
        "wardrobe": wardrobe,
        "gaps": gaps,
        "recent_searches": searches,
        "summary": lines[:5],
        "sources": {"m1": src_m1, "m3": src_m3, "m5": src_m5, "m7": src_m7},
    }


async def wardrobe(pro_id: str, client_id: str) -> dict:
    """The client's pieces (M1), to build a look with them (F4). Needs consent."""
    _require_consent(pro_id, client_id)
    items, src_m1 = await clients.wardrobe(client_id)
    worn, _ = await clients.wear_stats(client_id, [i["item_id"] for i in items])
    return {
        "client_id": client_id,
        "items": [
            {
                "item_id": i["item_id"],
                "category": i["category"],
                "subcategory": i.get("subcategory"),
                "color": (i.get("colors") or [{}])[0].get("name"),
                "wear_count": worn.get(i["item_id"], i.get("wear_count") or 0),
                "price_tnd": i.get("price_tnd"),
                "image": i.get("image_cutout") or i.get("image_raw"),
            }
            for i in items
        ],
        "sources": {"m1": src_m1},
    }


# ---------------------------------------------------------------- F2b · private conversation
def _has_access(pro_id: str, client_id: str) -> bool:
    return bool(store.links.find(pro_id=pro_id, client_id=client_id, status="active"))


def _chat_role(pro_id: str, client_id: str, person_id: str) -> str:
    """Only the two people of the conversation; the stylist only while the client gives access."""
    _pro(pro_id)
    if person_id == client_id:
        return "client"
    if person_id != pro_id:
        raise Forbidden("this conversation is private to the stylist and the client")
    if not _has_access(pro_id, client_id):
        raise Forbidden(f"client {client_id} has not given {pro_id} access (or revoked it)")
    return "stylist"


def conversation(pro_id: str, client_id: str, reader_id: str) -> dict:
    _chat_role(pro_id, client_id, reader_id)
    chat = store.chats.get(store.chat_key(pro_id, client_id)) or {"messages": []}
    # once the client revokes access, only the client can still read it, and nobody can write
    return {
        "pro_id": pro_id,
        "client_id": client_id,
        "can_write": _has_access(pro_id, client_id),
        "messages": chat["messages"],
    }


def post_message(pro_id: str, client_id: str, sender_id: str, text: str, look_id: str | None = None) -> dict:
    role = _chat_role(pro_id, client_id, sender_id)
    if not _has_access(pro_id, client_id):
        raise Forbidden("the conversation is closed: the client revoked the access")
    key = store.chat_key(pro_id, client_id)
    chat = store.chats.get(key) or {"pro_id": pro_id, "client_id": client_id, "messages": []}
    message = {
        "message_id": store.new_id("msg"),
        "sender_id": sender_id,
        "role": role,
        "text": text,
        "look_id": look_id,
        "created_at": store.now(),
    }
    chat["messages"].append(message)
    store.chats.put(key, chat)
    return message


def delete_conversation(pro_id: str, client_id: str, requester_id: str) -> None:
    """Right to be forgotten: the client deletes the whole conversation (the stylist cannot)."""
    if requester_id != client_id:
        raise Forbidden("only the client can delete the conversation")
    if not store.chats.delete(store.chat_key(pro_id, client_id)):
        raise NotFound("no conversation between this stylist and this client")


# ---------------------------------------------------------------- F3 · review of the style profile (BO4)
FIELDS = ("archetype", "likes", "dislikes", "colours")


async def review(client_id: str, body: dict) -> dict:
    _require_consent(body["pro_id"], client_id)
    profile, src = await clients.style_profile(client_id)
    before = {
        "archetype": profile.get("archetype"),
        "likes": profile.get("likes") or [],
        "dislikes": profile.get("dislikes") or [],
        "colours": profile.get("colours") or [],
    }
    after = body["corrections"]

    def same(field: str) -> bool:
        a, b = before[field], after[field]
        return (a or None) == (b or None) if field == "archetype" else set(a) == set(b)

    changed = [f for f in FIELDS if not same(f)]
    sent, _ = await clients.send_corrections(client_id, body["pro_id"], after)
    record = {
        "review_id": store.new_id("rev"),
        "pro_id": body["pro_id"],
        "client_id": client_id,
        "before": before,
        "corrections": after,
        "changed": changed,
        "agreement": round(1 - len(changed) / len(FIELDS), 3),
        "sent_to_m5": bool(sent),
        "note": body.get("note"),
        "created_at": store.now(),
        "sources": {"m5": src},
    }
    return store.reviews.put(record["review_id"], record)


def agreement() -> dict:
    """How often the M5 profile agrees with a professional: the evaluation of M5 by humans (F3)."""
    reviews = list(store.reviews.all().values())
    if not reviews:
        return {"n_reviews": 0, "overall": None, "per_field": {}}
    per_field = {f: round(sum(f not in r["changed"] for r in reviews) / len(reviews), 3) for f in FIELDS}
    return {
        "n_reviews": len(reviews),
        "overall": round(sum(r["agreement"] for r in reviews) / len(reviews), 3),
        "per_field": per_field,
    }


# ---------------------------------------------------------------- F4 · looks (BO7)
def _look_product(p: dict) -> dict:
    return {
        "product_id": p["product_id"],
        "item": p["product_name"],
        "shop": p["shop_name"],
        "price_tnd": p.get("price_tnd"),
        "image_url": p.get("image_url"),
        "image_path": p.get("image_path") or None,
        "product_url": p.get("product_url"),
    }


async def _products(product_ids: list[str]) -> tuple[list[dict], str]:
    """M7 products as they are in the catalogue (unknown id -> 404)."""
    out, source = [], "real"
    for pid in product_ids:
        found, source = await clients.product(pid)
        if found is None and source == "real":
            raise NotFound(f"unknown product {pid}")
        if found is not None:
            out.append(found)
    return out, source


async def send_look(body: dict) -> dict:
    _require_consent(body["pro_id"], body["client_id"])
    found, src_m7 = await _products(body["product_ids"])
    items, _ = await clients.wardrobe(body["client_id"])
    owned = [i for i in items if i["item_id"] in body["item_ids"]]  # the client's pieces of the look
    pieces = owned + [clients.product_as_garment(body["client_id"], p) for p in found]
    score, src_m2 = await clients.look_score(body["client_id"], pieces)
    card, src_m10 = await clients.share_card(body["client_id"], pieces, body.get("message"), body["language"])
    products = [_look_product(p) for p in found]
    prices = [p["price_tnd"] for p in products if p["price_tnd"] is not None]
    look = {
        "look_id": store.new_id("look"),
        "pro_id": body["pro_id"],
        "client_id": body["client_id"],
        "item_ids": body["item_ids"],
        "products": products,
        "total_price_tnd": round(sum(prices), 2) if prices else None,
        "score": score,
        **card,
        "message": body.get("message"),
        "created_at": store.now(),
        "sources": {"m2": src_m2, "m7": src_m7, "m10": src_m10},
    }
    store.looks.put(look["look_id"], look)
    # the look also lands in the private conversation, so the client sees it with the stylist's words
    post_message(
        body["pro_id"],
        body["client_id"],
        body["pro_id"],
        body.get("message") or "New look",
        look["look_id"],
    )
    return look


def list_looks(client_id: str | None = None, pro_id: str | None = None) -> list[dict]:
    equal = {k: v for k, v in {"client_id": client_id, "pro_id": pro_id}.items() if v}
    return store.looks.find(**equal)


# ---------------------------------------------------------------- F5 · in-store (BO5)
async def instore(body: dict) -> dict:
    pro = _pro(body["pro_id"])
    if pro["type"] != "boutique":
        raise Forbidden("in-store sessions are for boutique accounts")
    _require_consent(body["pro_id"], body["client_id"])
    found, src_m7 = await clients.product(body["product_id"])
    if found is None:
        raise NotFound(f"unknown product {body['product_id']}")
    if src_m7 == "real" and found["shop_name"] != pro["shop"]:
        raise Forbidden(f"{body['product_id']} is not sold by {pro['shop']}")
    product = _look_product(found)
    answer, src_m6 = await clients.verdict(body["client_id"], product, body["language"])
    return {
        "pro_id": body["pro_id"],
        "client_id": body["client_id"],
        "product": product,
        "verdict": answer["verdict"],
        "score": answer.get("score"),
        "reasons": answer.get("reasons") or [],
        "explanation": answer.get("explanation") or "",
        "sources": {"m6": src_m6, "m7": src_m7},
    }


# ---------------------------------------------------------------- F6 · dashboard (BO6)
async def get_dashboard(shop: str | None, days: int | None = None, sources: list[str] | None = None) -> dict:
    from modules.m07_local_catalogue import service as m7

    if not m7.knowledge_base_ready():
        return mock.dashboard(shop) | {"method": {"all": "mock: the M7 knowledge base is missing (dvc pull)"}}
    agent = await m7.get_agent()
    if shop and not any(p["shop_name"] == shop for p in agent.catalogue.products):
        raise NotFound(f"shop {shop!r} is not in the M7 catalogue")
    return await dashboard.build(shop, CONFIG, agent.catalogue, agent.encoder, days, sources)


async def get_insights(shop: str | None, days: int | None = None, sources: list[str] | None = None) -> dict:
    """2-3 tips for the boutique: written by the BO6 LLM from the dashboard figures, or by rules."""
    d = await get_dashboard(shop, days, sources)
    return await dashboard_insights.build(d, get_llm())


async def pro_dashboard(pro_id: str, days: int | None = None, sources: list[str] | None = None) -> dict:
    pro = _pro(pro_id)
    if pro["type"] != "boutique":
        raise Forbidden("the demand dashboard is for boutique accounts")
    return await get_dashboard(pro["shop"], days, sources)


# ---------------------------------------------------------------- F7 · hand-off (BO8)
async def check_escalation(body: dict) -> dict:
    """Rules first; on a longer chat they do not escalate, the BO6 LLM may add a signal (by_llm)."""
    decision = escalate.run(body["messages"], body.get("ai_confidence"), CONFIG)
    return await escalate.with_llm(decision, body["messages"], get_llm(), CONFIG)


async def _add_to_open(h: dict, messages: list[dict], body: dict) -> dict:
    """The client writes again while a request is open: add the new messages and refresh the facts."""
    known = {(m["role"], m["text"]) for m in h.get("messages", [])}
    new = [m for m in messages if (m["role"], m["text"]) not in known]
    if new:
        h["messages"] = [*h.get("messages", []), *new]
        said = summary.facts(h["messages"])  # the last occasion / budget / city said wins
        h |= {
            "occasion": body.get("occasion") or said["occasion"] or h.get("occasion"),
            "budget_tnd": body.get("budget_tnd") or said["budget_tnd"] or h.get("budget_tnd"),
            "city": body.get("city") or said["city"] or h.get("city"),
        }
        searches, _ = await clients.recent_searches(h["user_id"], 3)
        h["summary"] = await _summary(
            h["messages"], h["occasion"], h["budget_tnd"], h["city"], h["escalation"]["reason"], searches
        )
        at = store.now()
        h["history"].append({"status": "new_message", "pro_id": h["pro_id"], "at": at})
        h["updated_at"] = at
        store.handoffs.put(h["handoff_id"], h)
    return h | {"already_open": True}


async def _summary(messages, occasion, budget, city, reason, searches) -> list[str]:
    """Fact lines from code; the BO6 LLM may replace the raw first line by one clear sentence."""
    lines = summary.lines(messages, occasion, budget, city, reason, searches)
    sentence = await summary.llm_sentence(get_llm(), messages)
    if sentence:
        lines = [f"Summary (AI): {sentence}", *lines[1:]]
    return lines[:5]


def _open_load() -> dict[str, int]:
    return Counter(
        h["pro_id"] for h in store.handoffs.all().values() if h["status"] in ("queued", "accepted")
    )


async def create_handoff(body: dict) -> dict:
    messages = body["messages"]
    # One open request per client: new messages go into the request in progress (same stylist), so
    # nothing the client writes is lost and no duplicate request is created.
    for h in store.handoffs.find(user_id=body["user_id"]):
        if h["status"] in ("queued", "accepted"):
            return await _add_to_open(h, messages, body)
    decision = await check_escalation(body)
    if body.get("force"):
        decision = {**decision, "escalate": True, "reason": decision["reason"] or "user_choice"}
    said = summary.facts(messages)
    occasion = body.get("occasion") or said["occasion"]
    budget = body.get("budget_tnd") or said["budget_tnd"]
    city = body.get("city") or said["city"]
    at = store.now()
    record = {
        "handoff_id": store.new_id("hof"),
        "user_id": body["user_id"],
        "session_id": body["session_id"],
        "status": "not_needed",
        "pro_id": None,
        "candidates": [],
        "escalation": decision,
        "occasion": occasion,
        "budget_tnd": budget,
        "city": city,
        "summary": [],
        "messages": messages,
        "created_at": at,
        "updated_at": at,
        "history": [],
    }
    if not decision["escalate"]:
        return record  # not stored: nothing for a stylist to do
    profile, _ = await clients.style_profile(body["user_id"])
    searches, _ = await clients.recent_searches(body["user_id"], 3)
    candidates = match.rank(
        list(store.pros.all().values()),
        _open_load(),
        summary.wanted_words(messages, occasion),
        city,
        body["language"],
        profile.get("style_vector"),
        CONFIG,
    )
    record |= {
        "candidates": candidates,
        "summary": await _summary(messages, occasion, budget, city, decision["reason"], searches),
        "status": "queued" if candidates else "no_stylist",
        "pro_id": candidates[0]["pro_id"] if candidates else None,
    }
    record["history"].append({"status": record["status"], "pro_id": record["pro_id"], "at": at})
    return store.handoffs.put(record["handoff_id"], record)


def _link_from_handoff(pro_id: str, client_id: str) -> None:
    """The client asked for a stylist: the one who accepts gets access to the client's data (F2),
    which the client can revoke like any other access (DELETE /m14/clients/{link})."""
    for link in store.links.find(pro_id=pro_id, client_id=client_id):
        if link["status"] == "active":
            return
    at = store.now()
    link = {
        "link_id": store.new_id("lnk"),
        "pro_id": pro_id,
        "client_id": client_id,
        "status": "active",
        "message": "Help request (hand-off)",
        "created_at": at,
        "answered_at": at,
    }
    store.links.put(link["link_id"], link)


def queue(pro_id: str, status: str | None = None) -> list[dict]:
    _pro(pro_id)
    wanted = (status,) if status else ("queued", "accepted")
    items = [h for h in store.handoffs.find(pro_id=pro_id) if h["status"] in wanted]
    return sorted(items, key=lambda h: h["created_at"])


def get_handoff(handoff_id: str) -> dict:
    found = store.handoffs.get(handoff_id)
    if found is None:
        raise NotFound(f"unknown hand-off {handoff_id}")
    return found


def update_handoff(handoff_id: str, body: dict) -> dict:
    h = get_handoff(handoff_id)
    if h["pro_id"] != body["pro_id"]:
        raise Forbidden("this hand-off is not queued for you")
    allowed = {"queued": {"accepted", "declined"}, "accepted": {"closed"}}
    if body["status"] not in allowed.get(h["status"], set()):
        raise ValueError(f"cannot go from {h['status']} to {body['status']}")
    at = store.now()
    h["history"].append(
        {"status": body["status"], "pro_id": body["pro_id"], "note": body.get("note"), "at": at}
    )
    h |= {"status": body["status"], "updated_at": at}
    if body["status"] == "accepted":
        _link_from_handoff(body["pro_id"], h["user_id"])
    if body["status"] == "declined":  # next candidate who has not declined, or nobody left
        declined = {e["pro_id"] for e in h["history"] if e["status"] == "declined"}
        nxt = next((c for c in h["candidates"] if c["pro_id"] not in declined), None)
        h |= {"status": "queued" if nxt else "no_stylist", "pro_id": nxt["pro_id"] if nxt else None}
        h["history"].append({"status": h["status"], "pro_id": h["pro_id"], "at": at})
    return store.handoffs.put(handoff_id, h)
