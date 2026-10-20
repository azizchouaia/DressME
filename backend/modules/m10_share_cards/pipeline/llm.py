"""Calls the team's LLM layer (shared/llm.py → Anthropic / OpenAI / Ollama, chosen in infra/.env).

If no LLM is configured (no API key, package missing, network down) it returns None and the caller uses its
template fallback, so the app and the demo always work. The prompt is still built and shown in the trace.
"""

import re

from shared.config import settings

QUOTES = "\"'“”«»‘’"


def available() -> bool:
    return bool(settings.llm_model) and (bool(settings.llm_api_key) or settings.llm_provider == "ollama")


def clean(text: str, max_chars: int = 400, max_sentences: int | None = None) -> str:
    """Small local models often wrap the answer in quotes or run long: strip the quotes and cut on a
    sentence boundary (never in the middle of a word)."""
    text = " ".join(text.split()).strip().strip(QUOTES).strip()
    parts = re.split(r"(?<=[.!?])\s+", text)
    if max_sentences:
        parts = parts[:max_sentences]
    out = ""
    for p in parts:
        if len(out) + len(p) + 1 > max_chars:
            break
        out = f"{out} {p}".strip()
    return out or text[:max_chars].rsplit(" ", 1)[0]


def complete(system: str, user: str, max_chars: int = 400, max_sentences: int | None = None) -> str | None:
    if not available():
        return None
    try:
        from shared.llm import get_chat_model

        out = get_chat_model().invoke([("system", system), ("human", user)])
        text = (out.content if isinstance(out.content, str) else str(out.content)).strip()
        return clean(text, max_chars, max_sentences) or None
    except Exception:  # noqa: BLE001 — any provider error falls back to the template
        return None
