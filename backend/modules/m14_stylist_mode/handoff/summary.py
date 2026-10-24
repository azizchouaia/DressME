"""F7.c · what the stylist reads before answering: at most 5 lines. The facts (occasion, budget and city
read with M7's parser, the escalation reason, the client's recent local searches) come from code; the BO6
LLM (Qwen, llm.py) only adds one plain-English sentence of what the client wants, checked before use.
"""

import re

from modules.m07_local_catalogue.llm import numbers_ok
from modules.m07_local_catalogue.pipeline import context, parse
from modules.m07_local_catalogue.scraper.normalize import fold
from modules.m07_local_catalogue.taxonomy import city_from_text

REASONS = {
    "asks_human": "asked to talk to a stylist",
    "frustration": "the assistant does not meet their expectations",
    "complex_occasion": "important occasion, personal advice helps",
    "low_confidence": "the assistant is not sure of its answer",
    "long_conversation": "long conversation without a solution",
    "repeated_request": "repeats the same request",
    "user_choice": "chose to talk to a stylist",
}
# Occasions: the same lexicon as M7's search (pipeline/context.py: mariage, aïd, ramadan, plage...).
# The codes stay French (they match the stylists' specialities); the summary shows them in English.
OCCASIONS_EN = {code: o["en"] for code, o in context.OCCASIONS.items()}


def facts(messages: list[dict]) -> dict:
    """Occasion, budget and city said by the user (the last mention wins)."""
    occasion = budget = city = None
    for m in messages:
        if m["role"] != "user":
            continue
        text = fold(m["text"])
        # in one message the first occasion of the lexicon wins ("robe de soirée pour un mariage" -> mariage);
        # across messages the last one said wins
        occasion = context.occasion_of(text) or occasion
        _, high = parse.parse_price(text)
        budget = high or budget
        city = city_from_text(m["text"]) or city
    return {"occasion": occasion, "budget_tnd": budget, "city": city}


def wanted_words(messages: list[dict], occasion: str | None) -> set[str]:
    """Words of the conversation a stylist's speciality can match (occasion + pieces + 'homme', 'hijab')."""
    words = {fold(w) for m in messages if m["role"] == "user" for w in re.findall(r"\w+", m["text"])}
    return words | ({fold(occasion)} if occasion else set())


LLM_SYSTEM = (
    "You help a human fashion stylist in Tunisia. From the client's messages (French, English, "
    "Tunisian darija or Arabic), write ONE short sentence in English (at most 30 words): what the client "
    "wants and why a human is needed. Use only what the messages say. Do not add prices or numbers the "
    "client did not write."
)


async def llm_sentence(llm, messages: list[dict]) -> str | None:
    """One clear English sentence for the stylist (Qwen), checked: short, no invented number."""
    if not llm.on("handoff_summary"):
        return None
    chat = "\n".join(f"- {m['text']}" for m in messages if m["role"] == "user")
    text = await llm.text(LLM_SYSTEM, chat, max_tokens=90)
    if not text:
        return None
    text = text.strip().strip('"').splitlines()[0].strip()
    if not 10 <= len(text) <= 260 or not numbers_ok(text, chat):
        return None
    return text


def lines(
    messages: list[dict],
    occasion: str | None,
    budget: float | None,
    city: str | None,
    reason: str | None,
    searches: list[str],
) -> list[str]:
    asked = next((m["text"] for m in messages if m["role"] == "user"), "")
    last = next((m["text"] for m in reversed(messages) if m["role"] == "user"), "")
    out = [f"Request: {asked[:160]}"]
    context = [
        f"occasion: {OCCASIONS_EN.get(occasion, occasion)}" if occasion else None,
        f"budget: {budget:g} TND" if budget else None,
        f"city: {city}" if city else None,
    ]
    if any(context):
        line = " · ".join(c for c in context if c)
        out.append(line[0].upper() + line[1:])  # not capitalize(): it would lower "TND" and "Sousse"
    if reason:
        out.append(f"Why a human: {REASONS.get(reason, reason)}")
    if searches:
        out.append("Searched the shops for: " + ", ".join(searches[:3]))
    if last and last != asked:
        out.append(f"Last message: {last[:160]}")
    return out[:5]
