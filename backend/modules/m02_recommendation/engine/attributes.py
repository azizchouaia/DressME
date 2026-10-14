"""Context attributes of a piece (warmth, formality, mood), read from its FashionCLIP embedding.

Zero-shot: each attribute is a pair of text poles; the score is how much closer the image is to the "high"
pole than to the "low" one. Raw differences are z-scored with the mean / std measured on the 4.5k photos of
the
Kaggle clothing dataset (calibration), then squashed to 0..1. No labels needed, works on any new piece.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import artifacts

POLES: dict[str, tuple[list[str], list[str]]] = {
    "warmth": (
        [
            "a lightweight summer piece of clothing",
            "thin breathable clothing for hot weather",
            "a sleeveless or short-sleeved summer garment",
            "sandals or light summer shoes",
        ],
        [
            "a heavy warm winter piece of clothing",
            "thick clothing for cold weather",
            "a wool or padded garment for winter",
            "warm winter boots",
        ],
    ),
    "formality": (
        ["casual everyday clothing", "sporty streetwear", "loungewear or gym clothing", "casual sneakers"],
        [
            "formal business attire",
            "elegant evening wear",
            "a smart tailored office outfit piece",
            "formal leather dress shoes",
        ],
    ),
    "comfy": (
        ["a stiff structured tailored garment", "uncomfortable formal clothing"],
        ["soft relaxed comfortable clothing", "cozy loose-fitting loungewear"],
    ),
    "bold": (
        ["a plain understated neutral-coloured garment", "a basic minimal piece of clothing"],
        ["a bold eye-catching colourful statement piece", "a striking vibrant patterned garment"],
    ),
    "classy": (
        ["a sporty casual streetwear piece", "a cheap-looking basic garment"],
        ["an elegant refined classy piece", "a chic sophisticated luxury garment"],
    ),
}
ATTRS = list(POLES)
SLOPE = 1.6  # z-score -> sigmoid slope


class AttributeScorer:
    def __init__(self, path: Path = artifacts.PROMPTS):
        d = np.load(path)
        self.lo = {a: d[f"{a}_lo"] for a in ATTRS}
        self.hi = {a: d[f"{a}_hi"] for a in ATTRS}
        self.mu, self.sd = d["mu"], d["sd"]

    def raw(self, emb: np.ndarray) -> np.ndarray:
        """emb (N, 512) -> raw pole differences (N, n_attrs)."""
        return np.stack([(emb @ self.hi[a].T).mean(1) - (emb @ self.lo[a].T).mean(1) for a in ATTRS], 1)

    def __call__(self, emb: np.ndarray) -> list[dict[str, float]]:
        z = (self.raw(emb) - self.mu) / self.sd
        p = 1 / (1 + np.exp(-SLOPE * z))
        return [dict(zip(ATTRS, map(float, row), strict=True)) for row in p]


def build_prompt_file(embed_texts, reference_emb: np.ndarray, path: Path = artifacts.PROMPTS) -> None:
    """Embed the poles with FashionCLIP and calibrate on a reference set of item embeddings."""
    arrays = {}
    for a, (lo, hi) in POLES.items():
        arrays[f"{a}_lo"], arrays[f"{a}_hi"] = embed_texts(lo), embed_texts(hi)
    raw = np.stack(
        [
            (reference_emb @ arrays[f"{a}_hi"].T).mean(1) - (reference_emb @ arrays[f"{a}_lo"].T).mean(1)
            for a in ATTRS
        ],
        1,
    )
    np.savez(path, mu=raw.mean(0), sd=raw.std(0) + 1e-6, **arrays)
