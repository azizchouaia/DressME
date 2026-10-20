"""RAG retriever: TF-IDF vectors + cosine similarity over a small knowledge base (YAML).

Retrieval-Augmented Generation = 1) retrieve the most relevant documents for the request,
2) put them in the prompt, 3) let the LLM write using that context. Used by M10 (captions) and M15 (coach).
TF-IDF keeps it light (no GPU, no API); swapping in sentence embeddings later keeps the same interface.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass(frozen=True)
class Doc:
    id: str
    text: str
    tags: tuple[str, ...] = ()


class Retriever:
    def __init__(self, docs: list[Doc]):
        self.docs = docs
        self.vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vec.fit_transform([f"{d.text} {' '.join(d.tags)}" for d in docs])

    @classmethod
    def from_yaml(cls, path: Path) -> "Retriever":
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls([Doc(d["id"], d["text"], tuple(d.get("tags", []))) for d in raw])

    def search(self, query: str, k: int = 3) -> list[tuple[Doc, float]]:
        scores = cosine_similarity(self.vec.transform([query]), self.matrix)[0]
        best = scores.argsort()[::-1][:k]
        return [(self.docs[i], round(float(scores[i]), 3)) for i in best if scores[i] > 0]
