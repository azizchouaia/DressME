"""F7.a · should the assistant hand the conversation to a human stylist?

Stage 1 (this file): rules on the user's messages in FR / EN / darija (Latin letters) / Arabic, combined
with a noisy-OR: score = 1 - prod(1 - w) over the signals that fire (weights in config.yaml). Asking for
a human always escalates: missing that case costs more than a false alarm.
Stage 2 (later): a classifier trained on labelled chats replaces the lexicons, same output.
"""

import re

from modules.m07_local_catalogue.scraper.normalize import fold

LEXICON = {
    "asks_human": [
        r"\b(?:styliste|stylist|conseill\w*|personal shopper|human|humain\w*)\b",
        r"\bparler a (?:quelqu'?un|une personne|un humain)\b",
        r"\b(?:talk|speak|chat) (?:to|with) (?:someone|a person|a human|somebody)\b",
        r"\bvraie? personne\b|\breal person\b",
        r"\bn(?:7|h)eb nahki m3a\b|\bnahki m3a (?:wa7ed|had|bnadem)\b|\bbnadem\b",
        r"إنسان|مستشار|حد يعاوني|نحكي مع",
    ],
    "frustration": [
        r"\bca (?:marche|fonctionne) pas\b|\bn'importe quoi\b|\btu (?:ne )?comprends rien\b|\bnul\b",
        r"\buseless\b|\bnot helpful\b|\bdoesn'?t (?:work|help)\b|\bwrong again\b|\bstupid\b",
        r"\bma fhemt(?:ni)?ch\b|\bya5i\b|\b5ayeb\b|\bmouch hakka\b",
        r"ما فهمتنيش|ماهوش|خايب",
    ],
    "complex_occasion": [
        r"\bmariage\b|\bfiancailles\b|\bhenn?a\b|\boutia\b|\bsoutenance\b|\bentretien\b|\bgala\b|\bceremonie\b",
        r"\bwedding\b|\bengagement\b|\binterview\b|\bgraduation\b",
        r"\b3ers\b|\b3ors\b|\bkhotba\b|\b5otba\b|\bmlak\b",
        r"عرس|خطوبة|ملاك|حنة",
    ],
}
_COMPILED = {k: [re.compile(p) for p in v] for k, v in LEXICON.items()}


def _hits(signal: str, texts: list[str]) -> bool:
    return any(rx.search(t) for t in texts for rx in _COMPILED[signal])


def _repeated(texts: list[str]) -> bool:
    """The user says nearly the same thing 3 times: the assistant is not getting it."""
    words = [set(t.split()) for t in texts if len(t.split()) >= 2]
    for i, a in enumerate(words):
        similar = sum(len(a & b) / len(a | b) >= 0.6 for b in words[i + 1 :])
        if similar >= 2:
            return True
    return False


def run(messages: list[dict], ai_confidence: float | None, config: dict) -> dict:
    cfg = config["handoff"]
    weights = cfg["signals"]
    user = [fold(m["text"]) for m in messages if m["role"] == "user"]
    fired = {}
    for signal in ("asks_human", "frustration", "complex_occasion"):
        if _hits(signal, user):
            fired[signal] = weights[signal]
    if ai_confidence is not None and ai_confidence < cfg["low_confidence"]:
        fired["low_confidence"] = weights["low_confidence"]
    if len(user) >= cfg["long_conversation"]:
        fired["long_conversation"] = weights["long_conversation"]
    if _repeated(user):
        fired["repeated_request"] = weights["repeated_request"]
    keep = 1.0
    for w in fired.values():
        keep *= 1 - w
    score = round(1 - keep, 3)
    return {
        "escalate": "asks_human" in fired or score >= cfg["escalate_threshold"],
        "score": score,
        "reason": max(fired, key=fired.get) if fired else None,
        "signals": fired,
    }
