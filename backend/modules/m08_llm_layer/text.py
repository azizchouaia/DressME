"""Request parser: a chat sentence becomes the JSON the assistant acts on."""

from __future__ import annotations

import re

WEATHER = ("rainy", "rain", "cold", "hot", "snow", "snowy", "windy", "sunny", "warm")
SEASONS = ("spring", "summer", "autumn", "fall", "winter")
OCCASIONS = ("office", "work", "wedding", "party", "date", "gym", "travel", "casual", "formal")


def parse_request(message: str) -> dict:
    text = " ".join((message or "").lower().split())
    season = _first(text, SEASONS)
    if season == "fall":
        season = "autumn"
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
        "weather": _first(text, WEATHER) or "",
        "season": season or "",
        "occasion": _first(text, OCCASIONS) or "",
        "size": _size(text) or "",
        "budget": _budget(text),
        "query": text,
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
    return None
