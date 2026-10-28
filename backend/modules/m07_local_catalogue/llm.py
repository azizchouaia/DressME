"""BO6 LLM: Qwen 2.5 7B, run locally by Ollama, shared by the localshop agent (M7) and its M14 skill.

Where it is used (each one can be switched off in config.yaml -> llm):
- M7  understand: a request the rules do not understand at all ("nlawej 3la haja l 3ers mouch ghalia")
      -> type, colour, gender, budget, city as JSON, then the normal search runs with them;
- M14 handoff summary: one clear sentence for the stylist about what the client wants;
- M14 escalation: says if a longer chat asks for a human / is frustrated, next to the rules;
- M14 insights: two or three tips for a boutique, written from the dashboard figures.

The LLM never chooses a product, a price or a stylist. Its JSON is constrained by a schema (Ollama
structured outputs), then checked against the catalogue vocabulary; a number it writes must exist in the
facts it was given. When the LLM is off, slow or wrong, every caller keeps the rule-based answer.
"""

import json
import logging
import re

import httpx

from .paths import CONFIG

log = logging.getLogger("m07.llm")
_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


class LLM:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.enabled = bool(cfg.get("enabled"))
        self.model = cfg["model"]
        self.url = cfg["url"].rstrip("/")

    def on(self, use: str) -> bool:
        """The LLM is on and this use of it is switched on in config.yaml."""
        return self.enabled and bool((self.cfg.get("uses") or {}).get(use, True))

    async def _chat(self, system: str, user: str, fmt=None, max_tokens: int = 200) -> str | None:
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "keep_alive": self.cfg.get("keep_alive", "15m"),
            "options": {"temperature": self.cfg.get("temperature", 0), "num_predict": max_tokens},
        }
        if fmt is not None:
            body["format"] = fmt
        try:
            async with httpx.AsyncClient(timeout=self.cfg.get("timeout_s", 60)) as client:
                r = await client.post(f"{self.url}/api/chat", json=body)
                r.raise_for_status()
                return r.json()["message"]["content"]
        except Exception as exc:  # Ollama not running, model not pulled, timeout: the rules answer
            log.info("LLM %s unavailable: %s", self.model, exc)
            return None

    async def json(self, system: str, user: str, schema: dict, max_tokens: int = 200) -> dict | None:
        text = await self._chat(system, user, schema, max_tokens)
        if text is None:
            return None
        try:
            out = json.loads(text)
        except json.JSONDecodeError:
            log.info("LLM returned invalid JSON: %r", text[:200])
            return None
        return out if isinstance(out, dict) else None

    async def text(self, system: str, user: str, max_tokens: int = 160) -> str | None:
        out = await self._chat(system, user, None, max_tokens)
        return out.strip() if out else None


def numbers_ok(text: str, facts: str) -> bool:
    """Every number of the LLM's text appears in the facts it was given (no invented price or count)."""
    allowed = {n.replace(",", ".") for n in _NUMBER.findall(facts)}
    return all(n.replace(",", ".") in allowed for n in _NUMBER.findall(text))


_llm: LLM | None = None


def get_llm() -> LLM:
    global _llm
    if _llm is None:
        _llm = LLM(CONFIG.get("llm") or {"enabled": False, "model": "", "url": ""})
    return _llm
