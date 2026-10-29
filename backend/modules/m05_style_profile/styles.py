"""Style archetypes ("brique 1"): one FashionCLIP vector per style, and the style mix of any embedding.

The vectors come from M1 (text encoder, or mean image embedding when vector_source = images); M5 never
loads FashionCLIP itself. They are computed once per (style list version, M1 mode) and kept in memory.
"""

import asyncio
from dataclasses import dataclass

import numpy as np

from . import m01_client
from .config import StyleList, get_config, load_styles


def _unit(v: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.clip(norm, 1e-12, None)


def style_mix(item_vec, style_vecs, factor: float = 30.0) -> np.ndarray:
    """Softmax over the cosine similarities item <-> each style. Works on one vector or a (n, d) matrix."""
    items = _unit(np.asarray(item_vec, dtype=float))
    styles = _unit(np.asarray(style_vecs, dtype=float))
    sims = items @ styles.T
    e = np.exp(factor * (sims - sims.max(axis=-1, keepdims=True)))
    return e / e.sum(axis=-1, keepdims=True)


@dataclass
class StyleSpace:
    styles: StyleList
    vectors: np.ndarray  # (S, 512), L2-normalised
    factor: float

    @property
    def ids(self) -> list[str]:
        return self.styles.ids

    @property
    def version(self) -> str:
        return self.styles.version

    def mix(self, vec) -> np.ndarray:
        return style_mix(vec, self.vectors, self.factor)

    def as_dict(self, mix) -> dict[str, float]:
        return {s: round(float(p), 4) for s, p in zip(self.ids, mix, strict=True)}

    def to_array(self, mix: dict[str, float]) -> np.ndarray:
        return np.array([float(mix.get(s, 0.0)) for s in self.ids])

    def families(self, mix: dict[str, float]) -> dict[str, float]:
        out = {f: 0.0 for f in self.styles.families}
        for s, p in mix.items():
            if s in self.ids:
                out[self.styles.family_of(s)] += p
        return dict(sorted(((f, round(p, 4)) for f, p in out.items()), key=lambda kv: -kv[1]))

    def top(self, mix: dict[str, float], n: int = 3) -> list[dict]:
        best = sorted(((s, p) for s, p in mix.items() if s in self.ids), key=lambda kv: -kv[1])[:n]
        return [{"style": s, "family": self.styles.family_of(s), "share": round(p, 4)} for s, p in best]

    def labels(self) -> dict[str, str]:
        return {s.id: (s.label or s.id) for s in self.styles.styles}


async def build_space(styles: StyleList) -> StyleSpace:
    """vector_source text (or images without examples): text encoder; images: mean example embedding."""
    from_text = [s for s in styles.styles if not (s.vector_source == "images" and s.examples)]
    text_vecs = {}
    if from_text:
        vecs = await m01_client.embed_texts([s.description for s in from_text])
        text_vecs = {s.id: v for s, v in zip(from_text, vecs, strict=True)}
    vectors = []
    for s in styles.styles:
        if s.id in text_vecs:
            vectors.append(text_vecs[s.id])
        else:
            vectors.append(_unit(np.mean(await m01_client.embed_images(s.examples), axis=0)))
    return StyleSpace(styles, _unit(np.array(vectors, dtype=float)), get_config().style_mix_factor)


_cache: dict[tuple[str, str], StyleSpace] = {}
_lock = asyncio.Lock()


async def get_space(reload: bool = False) -> StyleSpace:
    """Style vectors of the current styles.json, for the current M1 mode (mock / real)."""
    styles = load_styles()
    key = (styles.version, m01_client.mode())
    if reload:
        _cache.pop(key, None)
    if key not in _cache:
        async with _lock:
            if key not in _cache:
                _cache[key] = await build_space(styles)
    return _cache[key]


def _reset() -> None:
    """Tests only."""
    _cache.clear()
