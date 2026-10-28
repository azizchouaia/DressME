"""Local LLM through Ollama (no API key, runs on the user's GPU). Default: Qwen2.5 3B Instruct, which supports
tool calling and fits a 4 GB GPU. Change with LLM_LOCAL_MODEL (e.g. qwen2.5:7b) / OLLAMA_URL."""

from __future__ import annotations

import os

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("LLM_LOCAL_MODEL", "qwen2.5:3b")


class LLMError(RuntimeError):
    pass


def chat(
    messages: list[dict], tools: list[dict] | None = None, temperature: float = 0.2, fmt: str | None = None
) -> dict:
    """One chat turn -> the assistant message {"role", "content", "tool_calls"?}."""
    body = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": temperature, "num_ctx": 8192},
    }
    if tools:
        body["tools"] = tools
    if fmt:
        body["format"] = fmt  # "json": constrained JSON output
    try:
        r = httpx.post(f"{OLLAMA_URL}/api/chat", json=body, timeout=180)
        r.raise_for_status()
    except httpx.HTTPError as e:
        raise LLMError(f"Ollama not reachable at {OLLAMA_URL} ({e}); start it with `ollama serve`") from e
    return r.json()["message"]


def available() -> dict:
    try:
        tags = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5).json()
        names = [m["name"] for m in tags.get("models", [])]
        return {"ollama": True, "model": MODEL, "model_installed": MODEL in names, "models": names}
    except httpx.HTTPError:
        return {"ollama": False, "model": MODEL, "model_installed": False, "models": []}
