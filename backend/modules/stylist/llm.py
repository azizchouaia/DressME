"""Moved to shared/local_llm.py (every agent uses the same local LLM)."""

from shared.local_llm import MODEL, OLLAMA_URL, LLMError, available, chat  # noqa: F401
