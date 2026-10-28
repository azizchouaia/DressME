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
    return combine(fired, cfg)


def combine(fired: dict[str, float], cfg: dict) -> dict:
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


# Stage 1b: the BO6 LLM (Qwen) reads longer chats the lexicons missed ("sma3ni chkoun ynajem y3awenni").
LLM_SYSTEM = (
    "You read a client's messages to a fashion shopping assistant in Tunisia (French, English, Tunisian "
    "darija in Latin letters, or Arabic). Answer true only when it is clearly said. asks_human: the client "
    "wants a real person or a stylist. frustrated: the client is unhappy with the assistant. "
    "important_occasion: a wedding, engagement, henna, Aid, interview or graduation. "
    "evidence: copy, word for word, the client's words that show it; '' when everything is false."
)
LLM_SCHEMA = {
    "type": "object",
    "properties": {
        **{k: {"type": "boolean"} for k in ("asks_human", "frustrated", "important_occasion")},
        "evidence": {"type": "string"},
    },
    "required": ["asks_human", "frustrated", "important_occasion", "evidence"],
}
_LLM_SIGNAL = {
    "asks_human": "asks_human",
    "frustrated": "frustration",
    "important_occasion": "complex_occasion",
}


def worth_asking(messages: list[dict]) -> bool:
    """A one-line request ("robe noire") is the assistant's job: the LLM is asked on longer chats only."""
    user = [m["text"] for m in messages if m["role"] == "user"]
    return len(user) >= 2 or sum(len(t.split()) for t in user) >= 8


async def with_llm(decision: dict, messages: list[dict], llm, config: dict) -> dict:
    """Rules first; when they do not escalate a longer chat, the LLM may add signals (never remove one)."""
    if decision["escalate"] or not llm.on("escalation") or not worth_asking(messages):
        return decision
    chat = "\n".join(f"- {m['text']}" for m in messages if m["role"] == "user")
    said = await llm.json(LLM_SYSTEM, chat, LLM_SCHEMA, max_tokens=80)
    if not said:
        return decision
    # Grounding: the LLM must quote the client's own words; a quote that is not in the chat is ignored.
    evidence = fold(str(said.get("evidence") or "")).strip(" .!?\"'")
    if len(evidence) < 4 or evidence not in fold(chat):
        return decision
    weights = config["handoff"]["signals"]
    fired = dict(decision["signals"])
    added = [s for k, s in _LLM_SIGNAL.items() if said.get(k) is True and s not in fired]
    if not added:
        return decision
    for s in added:
        fired[s] = weights[s]
    return combine(fired, config["handoff"]) | {"by_llm": True}
