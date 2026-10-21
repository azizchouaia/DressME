"""HTTP endpoints of M14. Included automatically by api/main.py.

M14 is implemented, so the router always serves service.py (mock.py stays for other BOs' offline tests).
"""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from . import service
from .contract import (
    Agreement,
    ChatMessage,
    ChatMessageIn,
    ClientBrief,
    ClientLink,
    ConsentIn,
    Conversation,
    Dashboard,
    EscalateIn,
    Escalation,
    Handoff,
    HandoffIn,
    HandoffUpdate,
    InstoreIn,
    InstoreOut,
    LinkIn,
    Look,
    LookIn,
    Pro,
    ProIn,
    ProUpdate,
    Review,
    ReviewIn,
    Wardrobe,
)
from .identity import CARD

router = APIRouter(prefix="/m14", tags=["M14 Stylist / boutique mode"])
Source = Literal["real", "simulated"]
Sources = Annotated[list[Source] | None, Query(description="Logs to read (default: config.yaml)")]
Days = Annotated[int | None, Query(ge=1, le=365)]


async def _call(fn, *args):
    try:
        out = fn(*args)
        return await out if hasattr(out, "__await__") else out
    except service.NotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except service.Forbidden as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/identity")
async def identity_card():
    """M14 is a skill of the BO6 agent `localshop`: the orchestrator calls localshop, not this module."""
    return CARD


# ---------------------------------------------------------------- F1 · accounts
@router.post("/pro", response_model=Pro)
async def create_pro(body: ProIn):
    """Stylist or boutique account (a boutique = a shop of the M7 catalogue, one account per shop)."""
    return await _call(service.create_pro, body.model_dump())


@router.get("/pro", response_model=list[Pro])
async def list_pros(type: Literal["stylist", "boutique"] | None = None, city: str | None = None):
    return await _call(service.list_pros, type, city)


@router.get("/pro/{pro_id}", response_model=Pro)
async def get_pro(pro_id: str):
    return await _call(service.get_pro, pro_id)


@router.patch("/pro/{pro_id}", response_model=Pro)
async def update_pro(pro_id: str, body: ProUpdate):
    return await _call(service.update_pro, pro_id, body.model_dump())


# ---------------------------------------------------------------- F2 · clients (consent) + brief
@router.post("/clients", response_model=ClientLink)
async def invite(body: LinkIn):
    """A pro invites a client; nothing is shared until the client accepts (POST .../consent)."""
    return await _call(service.invite, body.model_dump())


@router.get("/clients", response_model=list[ClientLink])
async def list_links(pro_id: str | None = None, client_id: str | None = None):
    """A pro's clients, or the pros a client gave access to (the client sees who has access)."""
    return await _call(service.list_links, pro_id, client_id)


@router.post("/clients/{link_id}/consent", response_model=ClientLink)
async def consent(link_id: str, body: ConsentIn):
    return await _call(service.consent, link_id, body.client_id, body.accept)


@router.delete("/clients/{link_id}", response_model=ClientLink)
async def revoke(link_id: str, client_id: str):
    """The client takes access back at any time."""
    return await _call(service.revoke, link_id, client_id)


@router.get("/clients/{client_id}/brief", response_model=ClientBrief)
async def brief(client_id: str, pro_id: str):
    """5-line client brief (M1 wardrobe, M3 wear, M5 style, localshop searches); needs consent."""
    return await _call(service.brief, pro_id, client_id)


@router.get("/clients/{client_id}/wardrobe", response_model=Wardrobe)
async def wardrobe(client_id: str, pro_id: str):
    """The client's pieces (M1) to build a look with; needs consent."""
    return await _call(service.wardrobe, pro_id, client_id)


# ---------------------------------------------------------------- F2b · private conversation
@router.get("/chat/{pro_id}/{client_id}", response_model=Conversation)
async def conversation(pro_id: str, client_id: str, reader_id: str):
    """Private conversation: `reader_id` must be this stylist (with access) or this client."""
    return await _call(service.conversation, pro_id, client_id, reader_id)


@router.post("/chat/{pro_id}/{client_id}", response_model=ChatMessage)
async def post_message(pro_id: str, client_id: str, body: ChatMessageIn):
    return await _call(service.post_message, pro_id, client_id, body.sender_id, body.text)


@router.delete("/chat/{pro_id}/{client_id}", status_code=204)
async def delete_conversation(pro_id: str, client_id: str, requester_id: str):
    """The client deletes the conversation (right to be forgotten)."""
    await _call(service.delete_conversation, pro_id, client_id, requester_id)


# ---------------------------------------------------------------- F3 · profile review (BO4)
@router.post("/clients/{client_id}/review", response_model=Review)
async def review(client_id: str, body: ReviewIn):
    """A stylist corrects the client's style profile; the corrections go to M5 as human labels."""
    return await _call(service.review, client_id, body.model_dump())


@router.get("/reviews/agreement", response_model=Agreement)
async def agreement():
    """How often the M5 profile agrees with the stylists (human evaluation of M5)."""
    return await _call(service.agreement)


# ---------------------------------------------------------------- F4 · looks (BO7)
@router.post("/looks", response_model=Look)
async def send_look(body: LookIn):
    return await _call(service.send_look, body.model_dump())


@router.get("/looks", response_model=list[Look])
async def list_looks(client_id: str | None = None, pro_id: str | None = None):
    return await _call(service.list_looks, client_id, pro_id)


# ---------------------------------------------------------------- F5 · in-store (BO5)
@router.post("/instore/session", response_model=InstoreOut)
async def instore(body: InstoreIn):
    """A seller checks a shop piece against the client's own wardrobe (M6 verdict)."""
    return await _call(service.instore, body.model_dump())


# ---------------------------------------------------------------- F6 · dashboard (BO6)
@router.get("/dashboard", response_model=Dashboard)
async def dashboard(
    shop: Annotated[str | None, Query(description="Shop of the M7 catalogue; empty = whole market")] = None,
    days: Days = None,
    source: Sources = None,
):
    return await _call(service.get_dashboard, shop, days, source)


@router.get("/pro/{pro_id}/dashboard", response_model=Dashboard)
async def pro_dashboard(pro_id: str, days: Days = None, source: Sources = None):
    """Dashboard of the boutique account's own shop."""
    return await _call(service.pro_dashboard, pro_id, days, source)


# ---------------------------------------------------------------- F7 · hand-off (BO8)
@router.post("/handoff/check", response_model=Escalation)
async def check(body: EscalateIn):
    """Should the assistant offer a human stylist? (nothing is stored)"""
    return await _call(service.check_escalation, body.model_dump())


@router.post("/handoff", response_model=Handoff)
async def create_handoff(body: HandoffIn):
    """Escalate if needed, pick the stylists, write the summary, queue it for the best one."""
    return await _call(service.create_handoff, body.model_dump())


@router.get("/handoff/queue", response_model=list[Handoff])
async def handoff_queue(pro_id: str, status: Literal["queued", "accepted", "closed"] | None = None):
    return await _call(service.queue, pro_id, status)


@router.get("/handoff/{handoff_id}", response_model=Handoff)
async def get_handoff(handoff_id: str):
    return await _call(service.get_handoff, handoff_id)


@router.patch("/handoff/{handoff_id}", response_model=Handoff)
async def update_handoff(handoff_id: str, body: HandoffUpdate):
    """accept / decline (goes to the next stylist) / close."""
    return await _call(service.update_handoff, handoff_id, body.model_dump())
