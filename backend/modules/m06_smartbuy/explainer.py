"""Smart Buy's own explanation writer (until / besides M8).

Our facts -> 2 short friendly sentences in EN / FR / Tunisian Arabic, written by a local LLM (Ollama, free).
Guardrails: the LLM only rewords. If it is off, slow, invents a number, or contradicts the verdict,
we use the template text. `source` says which one wrote it.
"""

import os
import re

VERDICT_WORD = {"buy": "Good buy", "think": "Think twice", "skip": "Skip it"}
LANG = {"en": "English", "fr": "French", "ar": "Tunisian Arabic (Darija) written in Latin letters"}

PROMPT = """You are Smart Buy, an honest friend who knows the user's closet. Never push to buy.
Write the advice in {lang}: 2 short sentences, max 45 words, no list, no emoji.
Start with the verdict. Use ONLY these facts, add no new numbers, brands or claims.
Verdict: {verdict}
Piece: {piece}{price}
Facts:
{facts}"""


def template(verdict: str, reasons: list[str]) -> str:
    return f"{VERDICT_WORD[verdict]}: " + "; ".join(reasons[:3]) + "."


def _numbers(text: str) -> set[str]:
    return {n.rstrip(".,").replace(",", ".") for n in re.findall(r"\d+(?:[.,]\d+)?", text)}


def _safe(text: str, facts_text: str, verdict: str) -> bool:
    """No invented numbers; does not tell the user to buy when the verdict is skip (and the reverse)."""
    if not text or len(text) > 400:
        return False
    if not _numbers(text) <= _numbers(facts_text):
        return False
    low = text.lower()
    if verdict == "skip" and re.search(r"\b(go for it|buy it|achète-le|ach[eè]te[- ]le|chri)\b", low):
        return False
    if verdict == "buy" and re.search(r"\b(skip it|don't buy|n'ach[eè]te pas|ma techrich)\b", low):
        return False
    return True


def llm(verdict: str, piece: str, reasons: list[str], price: float | None, language: str,
        timeout: float = 20.0) -> str | None:
    try:
        import httpx
        facts = "\n".join(f"- {r}" for r in reasons[:5])
        price_txt = f" at {price:g} TND" if price else ""
        prompt = PROMPT.format(lang=LANG.get(language, "English"), verdict=VERDICT_WORD[verdict].upper(),
                               piece=piece, price=price_txt, facts=facts)
        r = httpx.post(os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/chat", timeout=timeout, json={
            "model": os.environ.get("OLLAMA_MODEL", "llama3.1:8b"), "stream": False,
            "options": {"temperature": 0.3, "num_predict": 120},
            "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        text = " ".join(r.json()["message"]["content"].split()).strip('"')
        return text if _safe(text, facts + price_txt + piece, verdict) else None
    except Exception:  # noqa: BLE001 - the LLM is optional
        return None


def explain(verdict: str, piece: str, reasons: list[str], price: float | None = None, language: str = "en",
            mode: str = "own", timeout: float = 20.0) -> tuple[str, str]:
    """-> (text, source). mode: own (Ollama, template fallback) | template."""
    if mode == "own":
        text = llm(verdict, piece, reasons, price, language, timeout)
        if text:
            return text, "llm"
    return template(verdict, reasons), "template"
