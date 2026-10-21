"""Talk with one person. Groq writes the sentence. Taste owns the score and the memory."""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request

from shared.base_agent import BaseAgent
from shared.taste_agent import brief, learn, score_map

from .contract import TalkInput, TalkOutput
from .identity import CARD

URL = "https://api.groq.com/openai/v1/chat/completions"


def _facts(memory: dict, scores: dict[str, int]) -> str:
    scored = [f"{title} {score}" for title, score in scores.items()]
    return "\n".join(
        [
            f"Gender: {memory.get('gender') or 'undecided'}.",
            "Loves: " + (", ".join(memory.get("loves") or []) or "none yet") + ".",
            "Avoids: " + (", ".join(memory.get("avoids") or []) or "none yet") + ".",
            "Wardrobe saved: " + (", ".join(memory.get("wardrobe") or []) or "nothing saved yet") + ".",
            "Scores, use these numbers only: " + ("; ".join(scored[:6]) or "no scored look yet") + ".",
        ]
    )


def _ask(messages: list[dict]) -> str:
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return ""
    payload = {
        "model": os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
        "temperature": 0.4,
        "messages": messages,
        "response_format": {"type": "json_object"},
    }
    request = urllib.request.Request(
        URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "DressMe/1.0",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=40) as response:
        body = json.loads(response.read().decode("utf-8"))
    return ((body.get("choices") or [{}])[0].get("message") or {}).get("content") or ""


def _parse(raw: str) -> dict:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"reply": raw.strip(), "memories": []}
    memories = parsed.get("memories") if isinstance(parsed, dict) else []
    clean = []
    for item in memories if isinstance(memories, list) else []:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind")
        note = (item.get("text") or "").strip()
        if kind in {"like", "dislike"} and note:
            clean.append({"kind": kind, "text": note})
    reply = parsed.get("reply") if isinstance(parsed, dict) else ""
    return {"reply": reply or raw.strip(), "memories": clean[:3]}


class TalkAgent(BaseAgent[TalkInput, TalkOutput]):
    name = "talk"
    description = "Explain a choice from this person's taste and remember what they say."
    input_model = TalkInput
    output_model = TalkOutput

    async def run(self, inp: TalkInput) -> TalkOutput:
        memory = brief(inp.user_id)
        scores = score_map(inp.user_id, inp.candidates) if inp.candidates else {}
        titles = {item.get("id"): item.get("title") or item.get("id") for item in inp.candidates}
        named = {titles.get(piece_id, piece_id): score for piece_id, score in scores.items() if titles.get(piece_id)}
        facts = _facts(memory, named)
        system = (
            "You are DressMe, talking with one person about clothes. "
            "Answer in their language, in two or three short sentences. "
            "When they ask what to wear, name the first scored look and its number, then connect it to what they love. "
            "Quote a score only when it appears in the facts. "
            "When they state a lasting preference, add it to memories. Otherwise leave memories empty. "
            'Return JSON: {"reply": "...", "memories": [{"kind": "like" or "dislike", "text": "short clothing description"}]}\n'
            f"Facts:\n{facts}"
        )
        if not os.environ.get("GROQ_API_KEY"):
            reply = "Add GROQ_API_KEY and I can talk from this person's taste."
            memories = []
        else:
            try:
                raw = _ask([{"role": "system", "content": system}, {"role": "user", "content": inp.message or "What fits me?"}])
            except Exception:
                raw = ""
            parsed = _parse(raw or '{"reply": "I could not reach Groq just now.", "memories": []}')
            reply = parsed["reply"]
            memories = parsed["memories"]
        remembered = []
        for item in memories:
            piece_id = "said-" + hashlib.sha1(item["text"].encode("utf-8")).hexdigest()[:12]
            learn(inp.user_id, piece_id, item["kind"], title=item["text"], labels=["said"])
            remembered.append(item["text"])
        fresh = brief(inp.user_id)
        return TalkOutput(
            reply=reply,
            loves=fresh["loves"],
            avoids=fresh["avoids"],
            wardrobe=fresh["wardrobe"],
            scores=named,
            remembered=remembered,
            next_actions=CARD["handoff"],
            session_id=inp.session_id,
        )


Agent = TalkAgent
