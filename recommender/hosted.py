"""Call a hosted chat model through the OpenAI-compatible API.

Any provider that serves POST {base}/chat/completions can sit here:
OpenAI, Azure OpenAI, Groq, OpenRouter, Together, or a model you host.
Other Dressme modules keep calling the stylist HTTP API. They do not
talk to this provider themselves.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request


def chat_completion(
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict],
    tools: list[dict],
    timeout: float = 30,
) -> dict | None:
    if not base_url or not api_key or not model:
        return None
    payload = {"model": model, "messages": messages, "tools": tools, "tool_choice": "auto"}
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Dressme-stylist/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return None
    return message_from(body)


def message_from(body: dict) -> dict | None:
    choices = body.get("choices") or []
    if not choices:
        return None
    message = choices[0].get("message")
    return message if isinstance(message, dict) else None


def tool_calls(message: dict) -> list[dict]:
    calls = []
    for call in message.get("tool_calls") or []:
        function = call.get("function") or {}
        raw = function.get("arguments") or "{}"
        try:
            args = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            args = {}
        calls.append({"id": call.get("id") or function.get("name") or "call", "name": function.get("name"), "arguments": args})
    return calls
