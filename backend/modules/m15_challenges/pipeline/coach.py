"""LLM coach = Prompt Engineering + RAG (M15).

After each logged day:
1. RAG: retrieve the 2 most relevant tips for what happened (broken rules, risk level, challenge type)
   from knowledge/style_tips.yaml (TF-IDF + cosine similarity, shared retriever from M10).
2. PE: prompt with role, tone constraints, retrieved tips, facts (day, result, violations, suggested pieces,
   completion probability from the ML model) and the expected output format.
3. LLM through shared/llm.py; without a configured LLM the template below is used (if/else fallback).
Memory (memory.py): tips already given to this user in this challenge are skipped by the RAG, rules broken
again and again and the last days are added to the prompt, so the coach does not repeat itself and names the
recurring problem.
"""


from pathlib import Path

from modules.m10_share_cards.pipeline import llm
from modules.m10_share_cards.pipeline.rag import Retriever

RULE_WORDS = {
    "no_repeat": "wearing a piece twice", "color_theme": "the colour theme", "category_required":
    "the required piece", "capsule_limit": "the capsule limit", "local_brand": "the Tunisian brand piece",
    "min_items": "the number of pieces",
}  # fmt: skip

KB = Path(__file__).resolve().parents[1] / "knowledge" / "style_tips.yaml"
_retriever: Retriever | None = None

SYSTEM = (
    "You are the DressMe challenge coach for users in Tunisia. Be warm and concrete. "
    "Write exactly 2 short sentences, 35 words at most: the first reacts to today's result (and says how to "
    "fix a broken rule), the second names the suggested next outfit if one is given. "
    "Use only the facts and tips given; never invent clothes; no greeting, no percentages, no quotes. "
    "Use the memory: if a problem keeps coming back, name it kindly; never repeat advice already given."
)


def retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever.from_yaml(KB)
    return _retriever


def advise(
    *,
    challenge: str,
    rule_types: list[str],
    day: int,
    valid: bool,
    violations: list[str],
    suggestion: list[str],
    probability: float,
    risk: str,
    streak: int,
    language: str = "en",
    memory: dict | None = None,
    broken_rules: list[str] | None = None,
) -> dict:
    query = " ".join([*rule_types, *violations, risk, challenge, "motivation" if valid else ""])
    memory = memory or {"tips_given": [], "issues": {}, "recent": []}
    # rules broken again today: times = earlier days + today
    recurring = [(r, memory["issues"].get(r, 0) + 1) for r in dict.fromkeys(broken_rules or [])]
    recurring = [(r, n) for r, n in recurring if n >= 2]
    given = set(memory["tips_given"])
    ranked = retriever().search(query, k=2 + len(given))
    hits = [h for h in ranked if h[0].id not in given][:2] or ranked[:1]  # new advice first
    tips = [d.text for d, _ in hits]
    facts = (
        f"Challenge: {challenge} · day {day} · result: {'valid' if valid else 'not valid'}"
        + (f" · broken rules: {'; '.join(violations)}" if violations else "")
        + f" · streak: {streak} · completion probability: {round(probability * 100)}% ({risk})"
        + (f" · suggested next outfit: {', '.join(suggestion)}" if suggestion else "")
    )
    mem_lines = [f"- {RULE_WORDS.get(r, r)} broken {n} times in this challenge (today included)"
                 for r, n in recurring]  # fmt: skip
    mem_lines += [f"- day {d['day']}: {'valid' if d['valid'] else 'not valid'}, you said: {d['message']}"
                  for d in memory["recent"]]  # fmt: skip
    prompt = (
        "Tips (retrieved):\n"
        + "\n".join(f"- {t}" for t in tips)
        + f"\n\nFacts:\n{facts}"
        + ("\n\nMemory (earlier days of this user):\n" + "\n".join(mem_lines) if mem_lines else "")
        + f"\n\nWrite the coach message in language '{language}':"
    )
    text = llm.complete(SYSTEM, prompt, max_chars=320, max_sentences=3)
    source = "llm"
    if not text:
        source = "template"
        head = (
            f"Day {day} counts, streak {streak}!"
            if valid
            else f"Day {day} does not count: {violations[0]}."
            if violations
            else f"Day {day} logged."
        )
        if recurring:
            r, n = recurring[0]
            head += f" That is {n} times for {RULE_WORDS.get(r, r)}."
        tip = f" Tip: {tips[0]}" if tips and (not valid or risk != "on_track") else ""
        nxt = f" Next: {' + '.join(suggestion)}." if suggestion else ""
        text = head + tip + nxt
    return {
        "message": text,
        "source": source,
        "prompt": prompt,
        "retrieved": [{"id": d.id, "score": s, "text": d.text} for d, s in hits],
        "memory": {"tips_skipped": sorted(given), "recurring": recurring, "recent": len(memory["recent"])},
    }
