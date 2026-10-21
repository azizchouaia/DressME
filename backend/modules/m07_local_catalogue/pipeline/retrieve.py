"""Hybrid retrieval: FashionCLIP visual similarity (query text or probe photo vs product photos) + BM25.

The catalogue is a few thousand products, so every product is scored exactly (one matrix product);
no approximate index is needed. Scores are raw here and mapped to 0..1 in rerank.py.
"""

import math
import re
from collections import Counter

import numpy as np

from ..scraper.normalize import fold

_STOPWORDS = set("de du des la le les un une et a au aux en pour avec the of and for with in".split())


def tokenize(text: str) -> list[str]:
    """Folded words with a light plural strip, so 'baskets blanches' matches 'Basket blanche'."""
    tokens = []
    for token in re.findall(r"\w+", fold(text)):
        if token in _STOPWORDS or len(token) < 2:
            continue
        if len(token) > 3 and token[-1] in "sx" and not token.endswith("ss"):
            token = token[:-1]
        tokens.append(token)
    return tokens


class BM25:
    """Okapi BM25 over short product documents (name, category, colour, shop, city)."""

    def __init__(self, documents: list[list[str]], k1: float = 1.2, b: float = 0.75):
        self.k1, self.b = k1, b
        self.doc_freqs = [Counter(doc) for doc in documents]
        self.doc_len = np.array([len(doc) for doc in documents], dtype=np.float32)
        self.avgdl = float(self.doc_len.mean()) if len(documents) else 0.0
        df = Counter(term for doc in documents for term in set(doc))
        n = len(documents)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def scores(self, query: list[str]) -> np.ndarray:
        out = np.zeros(len(self.doc_freqs), dtype=np.float32)
        if not query or not self.avgdl:
            return out
        norm = self.k1 * (1 - self.b + self.b * self.doc_len / self.avgdl)
        for term in set(query):
            idf = self.idf.get(term)
            if idf is None:
                continue
            tf = np.array([freqs.get(term, 0) for freqs in self.doc_freqs], dtype=np.float32)
            out += idf * tf * (self.k1 + 1) / (tf + norm)
        return out


def visual_scores(query_vector: np.ndarray | None, embeddings: np.ndarray) -> np.ndarray | None:
    """Cosine similarity between one L2-normalised query vector and every product photo."""
    if query_vector is None:
        return None
    q = np.asarray(query_vector, dtype=np.float32).reshape(-1)
    q = q / max(float(np.linalg.norm(q)), 1e-12)
    return embeddings @ q


def run(catalogue, terms: list[str], query_vector: np.ndarray | None) -> tuple[np.ndarray | None, np.ndarray]:
    """(visual cosine or None, BM25 score) for every product of the catalogue."""
    return visual_scores(query_vector, catalogue.embeddings), catalogue.bm25.scores(terms)
