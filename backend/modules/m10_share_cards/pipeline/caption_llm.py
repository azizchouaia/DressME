"""LLM caption writer = Prompt Engineering + RAG (M10).

1. RAG: retrieve the 3 most relevant writing guidelines for this card (kind, pieces, brands) from
   knowledge/captions.yaml with TF-IDF + cosine similarity.
2. PE: build a structured prompt: role, constraints, retrieved context, card facts, few-shot example,
   output format (caption only).
3. Call the LLM through shared/llm.py; if no LLM is configured, use the template caption (if/else).
"""

from pathlib import Path

from . import caption as template
from . import llm
from .rag import Retriever

KB = Path(__file__).resolve().parents[1] / "knowledge" / "captions.yaml"
_retriever: Retriever | None = None

SYSTEM = (
    "You write social-media captions for DressMe, a Tunisian AI wardrobe app. "
    "Follow the guidelines exactly. Output the caption only, no quotes, no explanation."
)
FEW_SHOT = (
    "Example\nCard: outfit · pieces: linen shirt, beige chinos · subtitle: Tuesday · 24°C · work\n"
    "Caption: 24°C and a linen shirt: work mode, easy mode. #MadeWithDressMe"
)


def retriever() -> Retriever:
    global _retriever
    if _retriever is None:
        _retriever = Retriever.from_yaml(KB)
    return _retriever


def build_prompt(
    kind: str,
    labels: list[str],
    brands: list[str],
    title: str | None,
    subtitle: str | None,
    stats: list[tuple[str, str]],
    language: str = "en",
) -> tuple[str, list[dict]]:
    query = " ".join([kind, title or "", subtitle or "", *labels, *(["local brand"] if brands else [])])
    hits = retriever().search(query, k=3)
    context = "\n".join(f"- {d.text}" for d, _ in hits)
    facts = (
        f"Card: {kind} · pieces: {', '.join(labels) or 'none'}"
        + (f" · brands: {', '.join(brands)}" if brands else "")
        + (f" · title: {title}" if title else "")
        + (f" · subtitle: {subtitle}" if subtitle else "")
        + (f" · stats: {'; '.join(f'{a} = {b}' for a, b in stats)}" if stats else "")
    )
    user = (
        f"Guidelines (retrieved):\n{context}\n\n{FEW_SHOT}\n\n"
        f"Now write the caption in language '{language}', max 2 sentences.\n{facts}\nCaption:"
    )
    return user, [{"id": d.id, "score": s, "text": d.text} for d, s in hits]


def write(
    kind: str,
    labels: list[str],
    brands: list[str],
    title: str | None,
    subtitle: str | None,
    stats: list[tuple[str, str]],
    language: str = "en",
) -> dict:
    prompt, docs = build_prompt(kind, labels, brands, title, subtitle, stats, language)
    text = llm.complete(SYSTEM, prompt)
    source = "llm"
    if not text:
        text, source = template.caption(kind, labels, title, stats, language), "template"
    return {"caption": text, "source": source, "prompt": prompt, "retrieved": docs}
