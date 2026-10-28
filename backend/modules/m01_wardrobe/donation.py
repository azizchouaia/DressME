"""Donation suggestions for a duplicated piece: retrieval in a verified list + a local LLM that picks and explains.

    piece + city ─► retrieve the places of donation_places.json that serve this city and category
                 ─► local LLM (Ollama, config `donation.llm`) picks up to `max_suggestions` and writes why
                 ─► validated: unknown place ids dropped; names, links and contacts come from the file only

The LLM never writes a link. When it is unreachable or answers nonsense, the places are returned in the
file's order with their own text (`llm_used=false`), so the donation screen always works.
"""

import json
import time
from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel, Field, ValidationError

from .config import MODULE_DIR, get_config
from .contract import DonationPlace, DonationSuggestion, DonationSuggestionsResponse, WardrobeItem

# place type -> the value stored by POST /donate when the user picks it
PLACE_OF_TYPE = {
    "association": DonationPlace.association,
    "community": DonationPlace.association,
    "collection": DonationPlace.other,
    "personal": DonationPlace.friend,
}

PROMPT = """You help a user in Tunisia give away a piece of clothing they own twice.
Rank the {k} best places for THIS piece among the candidates below, best first, and write one short
reason for each (max 20 words) that refers to the piece (its type, material or seasons). Then write one
friendly sentence for the user. Write the reasons and the sentence in French.
Use only the candidate ids. Use only the facts given about the piece: never guess its condition or size.
Do not write links, phone numbers or addresses.

PIECE
{piece}

USER'S CITY: {city}

CANDIDATES
{candidates}

Answer JSON only: {{"suggestions": [{{"place_id": "...", "reason": "..."}}], "message": "..."}}"""


class _Pick(BaseModel):
    place_id: str
    reason: str = Field(max_length=300)


class _Answer(BaseModel):
    suggestions: list[_Pick]
    message: str = Field(max_length=400)


_override: BaseChatModel | None = None  # tests put a scripted model here


def set_model(model: BaseChatModel | None) -> None:
    global _override
    _override = model


def _model() -> BaseChatModel:
    if _override is not None:
        return _override
    from langchain_ollama import ChatOllama

    c = get_config().donation.llm
    return ChatOllama(
        model=c.model, base_url=c.base_url, temperature=c.temperature, reasoning=False, format="json",
        client_kwargs={"timeout": c.timeout_s},
    )


def _model_name() -> str:
    return type(_override).__name__ if _override is not None else get_config().donation.llm.model


@lru_cache
def load_places() -> dict:
    path = MODULE_DIR / get_config().donation.places_file
    return json.loads(path.read_text(encoding="utf-8"))


def retrieve(item: WardrobeItem, city: str | None) -> list[dict]:
    """The places that serve this city and accept this category (file order)."""
    category = item.category.value
    out = []
    for p in load_places()["places"]:
        serves = "*" in p["cities"] or (city is not None and city in p["cities"])
        accepts = "*" in p["accepts"] or category in p["accepts"]
        if serves and accepts:
            out.append(p)
    return out


def describe(item: WardrobeItem) -> str:
    colours = ", ".join(c.name for c in item.colors[:2]) or "unknown colour"
    parts = [
        f"type: {item.subcategory or item.category.value} ({item.category.value})",
        f"colour: {colours}",
        f"material: {item.material or 'unknown'}",
        f"seasons: {', '.join(item.season) or 'unknown'}",
        f"worn {item.wear_count} times",
    ]
    if item.local_tag:
        parts.append(f"traditional piece: {item.local_tag}")
    return "; ".join(parts)


def _suggestion(p: dict, reason: str) -> DonationSuggestion:
    return DonationSuggestion(
        place_id=p["id"], name=p["name"], type=p["type"], place=PLACE_OF_TYPE[p["type"]], url=p.get("url"),
        phone=p.get("phone"), address=p.get("address"), how=p["how"], reason=reason,
    )


async def suggest(item: WardrobeItem, city: str | None) -> DonationSuggestionsResponse:
    t0 = time.perf_counter()
    k = get_config().donation.max_suggestions
    candidates = retrieve(item, city)
    by_id = {p["id"]: p for p in candidates}
    picks: list[DonationSuggestion] = []
    message, used = "", False
    if candidates:
        listing = "\n".join(f"- id={p['id']}: {p['name']} ({p['type']}). Best for: {p['best_for']}" for p in candidates)
        prompt = PROMPT.format(k=k, piece=describe(item), city=city or "unknown", candidates=listing)
        try:
            raw = (await _model().ainvoke(prompt)).content
            answer = _Answer.model_validate_json(raw if isinstance(raw, str) else json.dumps(raw))
            seen = set()
            for pick in answer.suggestions:
                if pick.place_id in by_id and pick.place_id not in seen:  # ids outside the list are dropped
                    seen.add(pick.place_id)
                    picks.append(_suggestion(by_id[pick.place_id], pick.reason.strip()))
            picks, message, used = picks[:k], answer.message.strip(), bool(picks)
            for p in candidates:  # the LLM ranked too few: complete with the list's order
                if len(picks) >= min(k, len(candidates)):
                    break
                if p["id"] not in seen:
                    picks.append(_suggestion(p, p["best_for"]))
        except Exception as e:
            if not _is_expected(e):
                raise
    if not used:
        picks = [_suggestion(p, p["best_for"]) for p in candidates[:k]]
        message = "Voici quelques idées pour donner cette pièce."
    return DonationSuggestionsResponse(
        item_id=item.item_id,
        city=city,
        suggestions=picks,
        message=message or "Voici où cette pièce peut faire plaisir.",
        llm_used=used,
        model=_model_name() if used else None,
        elapsed_ms=round((time.perf_counter() - t0) * 1000, 1),
    )


def _is_expected(e: Exception) -> bool:
    """LLM unreachable, model missing, timeout or unusable answer: fall back to the list."""
    import httpx

    try:
        from ollama import ResponseError
    except ImportError:
        ResponseError = ()  # noqa: N806
    return isinstance(e, (ValidationError, ValueError, OSError, httpx.HTTPError, ResponseError, ImportError))
