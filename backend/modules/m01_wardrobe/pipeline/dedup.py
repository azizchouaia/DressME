"""Duplicate groups: pairs above a similarity threshold, merged with union-find."""

from collections.abc import Iterable, Sequence

import numpy as np


class UnionFind:
    def __init__(self):
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:                    # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[max(ra, rb)] = min(ra, rb)


def group_pairs(pairs: Iterable[tuple[str, str]]) -> list[list[str]]:
    """[(a, b), (b, c), (d, e)] -> [[a, b, c], [d, e]] (sorted, deterministic)."""
    uf = UnionFind()
    for a, b in pairs:
        uf.union(a, b)
    groups: dict[str, list[str]] = {}
    for x in uf.parent:
        groups.setdefault(uf.find(x), []).append(x)
    return sorted(sorted(g) for g in groups.values() if len(g) > 1)


def pairs_above(ids: Sequence[str], vectors: np.ndarray, threshold: float) -> list[tuple[str, str]]:
    """Brute-force pairs with cosine similarity > threshold (vectors are L2-normalised)."""
    if len(ids) < 2:
        return []
    sims = vectors @ vectors.T
    i, j = np.triu_indices(len(ids), k=1)
    hit = sims[i, j] > threshold
    return [(ids[a], ids[b]) for a, b in zip(i[hit], j[hit], strict=True)]
