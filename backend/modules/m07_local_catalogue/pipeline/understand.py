"""LLM understanding of a request the rules did not understand at all (M7, BO6 LLM, see llm.py).

"nlawej 3la haja l 3ers mouch ghalia" -> the rules find no piece, colour or photo. The LLM rewrites it in
plain French and fills type / colour / gender / budget / city from a fixed vocabulary (JSON schema with
enums, so it cannot answer outside the catalogue). Then the code checks it: a budget must be a number
written in the request, a city a known Tunisian city said in the request, a gender one the request says
(rules of parse.py). The normal search runs
on the result; the LLM never sees nor picks the products.
"""

import re

from ..llm import LLM
from ..scraper.normalize import fold
from ..taxonomy import COLOR_CODES, SUBCATEGORIES, canonical_city
from . import parse

NONE = "none"
SYSTEM = (
    "You turn a clothing shopping request from Tunisia (French, English, Tunisian darija in Latin letters "
    "with digits 3, 7, 9, 5 for Arabic sounds, or Arabic) into search filters for a catalogue of shops.\n"
    "- subcategory: the ONE piece the person most likely needs. Think about the use: the beach -> swimwear, "
    "a cold winter -> coat, a job interview -> suit, a wedding or an engagement -> dress, the gym -> "
    "sneakers, the sun in the eyes -> sunglasses, a gift for a woman -> bag. 'none' only if no piece fits.\n"
    "- french: 2 to 5 French words naming that piece, for example 'manteau chaud' or 'robe de soirée'.\n"
    "- color, gender, max_price_tnd, city: only when the request says them; otherwise 'none', 0 or ''."
)
# No worked examples in the prompt: a small model copies them into unrelated answers.
SCHEMA = {
    "type": "object",
    "properties": {
        "french": {"type": "string"},
        "subcategory": {"type": "string", "enum": [*SUBCATEGORIES, NONE]},
        "color": {"type": "string", "enum": [*COLOR_CODES, NONE]},
        "gender": {"type": "string", "enum": ["women", "men", NONE]},
        "max_price_tnd": {"type": "number"},
        "city": {"type": "string"},
    },
    "required": ["french", "subcategory", "color", "gender", "max_price_tnd", "city"],
}
_ARABIC = re.compile(r"[؀-ۿ]")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def check(raw: dict, query: str) -> dict:
    """Keep only what is valid for the catalogue and actually said in the request."""
    folded = fold(query)
    said_numbers = {float(n.replace(",", ".")) for n in _NUMBER.findall(folded)}
    out: dict = {}
    french = str(raw.get("french") or "").strip()
    if 2 <= len(french) <= 120:
        out["query"] = french
    if raw.get("subcategory") in SUBCATEGORIES:
        out["subcategory"] = raw["subcategory"]
    if raw.get("color") in COLOR_CODES:
        out["color"] = raw["color"]
    if raw.get("gender") in ("women", "men") and raw["gender"] == parse.gender_from_query(folded):
        out["gender"] = raw["gender"]  # a gender the request does not say is dropped
    price = raw.get("max_price_tnd")
    if isinstance(price, int | float) and price > 0 and float(price) in said_numbers:
        out["max_price_tnd"] = float(price)  # a budget the request does not write is dropped
    city = canonical_city(str(raw.get("city") or ""))
    if city and (fold(city) in folded or _ARABIC.search(query)):
        out["city"] = city
    return out


async def run(llm: LLM, query: str) -> dict | None:
    """Validated slots for the search, or None (LLM off / failed / nothing usable)."""
    raw = await llm.json(SYSTEM, f"Request: {query}", SCHEMA, max_tokens=120)
    if not raw:
        return None
    slots = check(raw, query)
    return slots if set(slots) - {"query"} or slots.get("query") else None
