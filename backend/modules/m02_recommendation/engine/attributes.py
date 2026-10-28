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
# Warmth is absolute (a coat is warmer than a t-shirt). Formality and mood are relative to the category,
# otherwise every shoe looks "formal" next to clothes and lifts any outfit.
PER_CATEGORY = {"formality", "comfy", "bold", "classy"}
SLOPE = 1.6  # z-score -> sigmoid slope


class AttributeScorer:
    def __init__(self, path: Path = artifacts.PROMPTS):
        self.self_calibrate = not Path(path).exists()
        if self.self_calibrate:  # no Kaggle demo build: embed the poles now, calibrate on the user's own pieces
            from . import encoder

            self.lo = {a: encoder.embed_texts(POLES[a][0]) for a in ATTRS}
            self.hi = {a: encoder.embed_texts(POLES[a][1]) for a in ATTRS}
            self.mu, self.sd, self.cat_mu, self.cat_sd = 0.0, 1.0, {}, {}
            return
        d = np.load(path)
        self.lo = {a: d[f"{a}_lo"] for a in ATTRS}
        self.hi = {a: d[f"{a}_hi"] for a in ATTRS}
        self.mu, self.sd = d["mu"], d["sd"]
        # per-category calibration: a t-shirt is compared with other tops, a shoe with other shoes
        cats = [str(c) for c in d["cats"]] if "cats" in d else []
        self.cat_mu = {c: d[f"mu_{c}"] for c in cats}
        self.cat_sd = {c: d[f"sd_{c}"] for c in cats}

    def raw(self, emb: np.ndarray) -> np.ndarray:
        """emb (N, 512) -> raw pole differences (N, n_attrs)."""
        return np.stack([(emb @ self.hi[a].T).mean(1) - (emb @ self.lo[a].T).mean(1) for a in ATTRS], 1)

    def __call__(self, emb: np.ndarray, categories: list[str] | None = None) -> list[dict[str, float]]:
        raw = self.raw(emb)
        if self.self_calibrate:  # relative to this wardrobe: warmest / most formal of YOUR pieces score high
            z = (raw - raw.mean(0)) / (raw.std(0) + 0.02)
            return [dict(zip(ATTRS, map(float, row), strict=True)) for row in 1 / (1 + np.exp(-SLOPE * z))]
        cats = categories or [""] * len(emb)
        glob = np.array([a not in PER_CATEGORY for a in ATTRS])
        mu = np.stack([np.where(glob, self.mu, self.cat_mu.get(_group(c), self.mu)) for c in cats])
        sd = np.stack([np.where(glob, self.sd, self.cat_sd.get(_group(c), self.sd)) for c in cats])
        z = (raw - mu) / sd
        p = 1 / (1 + np.exp(-SLOPE * z))
        return [dict(zip(ATTRS, map(float, row), strict=True)) for row in p]


def _group(category: str) -> str:
    return {"traditional": "dress"}.get(category, category)


def build_prompt_file(
    embed_texts,
    reference_emb: np.ndarray,
    categories: list[str] | None = None,
    path: Path = artifacts.PROMPTS,
) -> None:
    """Embed the poles with FashionCLIP and calibrate them on reference item embeddings (globally and, when
    categories are given, per category)."""
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
    if categories:
        cats = np.array([_group(c) for c in categories])
        for c in sorted(set(cats)):
            arrays[f"mu_{c}"], arrays[f"sd_{c}"] = raw[cats == c].mean(0), raw[cats == c].std(0) + 1e-6
        arrays["cats"] = np.array(sorted(set(cats)))
    np.savez(path, mu=raw.mean(0), sd=raw.std(0) + 1e-6, **arrays)
