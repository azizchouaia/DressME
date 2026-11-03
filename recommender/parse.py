"""Turn a chat message into the JSON the stylist acts on."""

from __future__ import annotations

import re

INTENTS = ("feedback", "outfit", "search")
WEATHER = ("rainy", "rain", "cold", "hot", "snow", "snowy", "windy", "sunny", "warm")
SEASONS = ("spring", "summer", "autumn", "fall", "winter")
OCCASIONS = ("office", "work", "wedding", "party", "date", "gym", "travel", "casual", "formal")


def parse_request(message: str) -> dict:
    """Always returns JSON. Form fields can override empty values later."""

    text = " ".join((message or "").lower().split())
    budget = _budget(text)
    size = _size(text)
    weather = _first(text, WEATHER)
    season = _first(text, SEASONS)
    if season == "fall":
        season = "autumn"
    occasion = _first(text, OCCASIONS)
    feedback = None
    if any(word in text for word in ("dislike", "hate", "not this", "don't", "dont")):
        feedback = "dislike"
    elif any(word in text for word in ("like", "love", "save", "perfect")):
        feedback = "like"
    if feedback:
        intent = "feedback"
    elif any(word in text for word in ("outfit", "wear", "dress", "what should")) or not text:
        intent = "outfit"
    else:
        intent = "search"
    return {
        "intent": intent,
        "feedback": feedback,
        "weather": weather or "",
        "season": season or "",
        "occasion": occasion or "",
        "size": size or "",
        "budget": budget,
        "query": text,
    }


def merge_conditions(parsed: dict, weather: str, season: str, occasion: str, size: str, budget: float | None) -> dict:
    """Explicit form fields win. The sentence fills whatever the form left blank."""

    return {
        "intent": parsed["intent"],
        "feedback": parsed["feedback"],
        "weather": weather or parsed["weather"],
        "season": season or parsed["season"],
        "occasion": occasion or parsed["occasion"],
        "size": size or parsed["size"],
        "budget": budget if budget is not None else parsed["budget"],
        "query": parsed["query"],
    }


def _first(text: str, words: tuple[str, ...]) -> str | None:
    for word in words:
        if re.search(rf"\b{re.escape(word)}\b", text):
            return word
    return None


def _budget(text: str) -> float | None:
    match = re.search(r"(?:under|below|budget|less than)\s*\$?\s*(\d+(?:\.\d+)?)", text)
    if match is None:
        match = re.search(r"\$\s*(\d+(?:\.\d+)?)", text)
    if match is None:
        return None
    return float(match.group(1))


def _size(text: str) -> str | None:
    match = re.search(r"\bsize\s+([a-z0-9]+)\b", text)
    if match:
        return match.group(1).upper()
    match = re.search(r"\b(xxs|xs|s|m|l|xl|xxl|\d{2})\b", text)
    if match and any(word in text for word in ("size", "fit")):
        return match.group(1).upper()
    return None
