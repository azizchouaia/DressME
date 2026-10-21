"""F7.c · what the stylist reads before answering: at most 5 lines, built only from facts of the chat
(occasion, budget and city read with M7's parser), the escalation reason and the client's recent local
searches. No LLM here, so nothing is invented; M8 can reword it later without adding facts.
"""

import re

from modules.m07_local_catalogue.pipeline import parse
from modules.m07_local_catalogue.scraper.normalize import fold
from modules.m07_local_catalogue.taxonomy import city_from_text

OCCASIONS = {
    "mariage": r"\bmariage\b|\bwedding\b|\b3[eo]rs\b|عرس",
    "fiançailles": r"\bfiancailles\b|\bengagement\b|\bkhotba\b|\b5otba\b|خطوبة",
    "henna": r"\bhenn?a\b|\boutia\b|حنة",
    "entretien": r"\bentretien\b|\binterview\b",
    "soutenance": r"\bsoutenance\b|\bgraduation\b",
    "travail": r"\bbureau\b|\btravail\b|\boffice\b|\bwork\b",
    "soirée": r"\bsoiree\b|\bgala\b|\bparty\b|\bfete\b",
    "aïd": r"\baid\b|\beid\b|عيد",
}
_OCCASION_RES = {k: re.compile(v) for k, v in OCCASIONS.items()}

REASONS_FR = {
    "asks_human": "demande à parler à un styliste",
    "frustration": "l'assistant ne répond pas à ses attentes",
    "complex_occasion": "occasion importante, conseil personnalisé utile",
    "low_confidence": "l'assistant n'est pas sûr de sa réponse",
    "long_conversation": "longue conversation sans solution",
    "repeated_request": "répète la même demande",
    "user_choice": "a choisi de parler à un styliste",
}


def facts(messages: list[dict]) -> dict:
    """Occasion, budget and city said by the user (the last mention wins)."""
    occasion = budget = city = None
    for m in messages:
        if m["role"] != "user":
            continue
        text = fold(m["text"])
        # in one message the first occasion of OCCASIONS wins ("robe de soirée pour un mariage" -> mariage);
        # across messages the last one said wins
        occasion = next((name for name, rx in _OCCASION_RES.items() if rx.search(text)), occasion)
        _, high = parse.parse_price(text)
        budget = high or budget
        city = city_from_text(m["text"]) or city
    return {"occasion": occasion, "budget_tnd": budget, "city": city}


def wanted_words(messages: list[dict], occasion: str | None) -> set[str]:
    """Words of the conversation a stylist's speciality can match (occasion + pieces + 'homme', 'hijab')."""
    words = {fold(w) for m in messages if m["role"] == "user" for w in re.findall(r"\w+", m["text"])}
    return words | ({fold(occasion)} if occasion else set())


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
    out = [f"Demande : {asked[:160]}"]
    context = [
        f"occasion : {occasion}" if occasion else None,
        f"budget : {budget:g} TND" if budget else None,
        f"ville : {city}" if city else None,
    ]
    if any(context):
        line = " · ".join(c for c in context if c)
        out.append(line[0].upper() + line[1:])  # not capitalize(): it would lower "TND" and "Sousse"
    if reason:
        out.append(f"Pourquoi un humain : {REASONS_FR.get(reason, reason)}")
    if searches:
        out.append("A cherché dans les boutiques : " + ", ".join(searches[:3]))
    if last and last != asked:
        out.append(f"Dernier message : {last[:160]}")
    return out[:5]
