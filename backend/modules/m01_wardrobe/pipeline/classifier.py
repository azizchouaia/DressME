"""Zero-shot attributes from an image embedding. Pure logic: any object with `zero_shot()` works."""

from dataclasses import dataclass
from typing import Protocol

import numpy as np

from shared.schemas import GarmentCategory

from ..config import M01Config, get_config


class ZeroShotModel(Protocol):
    def zero_shot(
        self, image_emb: np.ndarray, prompts: tuple[str, ...], scale: float | None = None
    ) -> np.ndarray:
        ...


@dataclass
class Attributes:
    category: GarmentCategory
    subcategory: str
    local_tag: str | None
    confidence: float          # probability of the chosen category (sum over its subcategories)
    season: list[str]
    pattern: str
    material: str
    formality: float


def softmax(x: np.ndarray) -> np.ndarray:
    z = np.exp(x - np.max(x))
    return z / z.sum()


def describe(model: ZeroShotModel, image_emb: np.ndarray, cfg: M01Config | None = None) -> Attributes:
    cfg = cfg or get_config()
    t = cfg.prompt_template

    def head(name: str, labels) -> np.ndarray:
        return model.zero_shot(image_emb, tuple(s.text(t) for s in labels), cfg.logit_scales.get(name))

    subs = cfg.subcategories
    p_sub = head("subcategories", subs)
    by_category: dict[GarmentCategory, float] = {}
    for s, p in zip(subs, p_sub, strict=True):
        by_category[s.category] = by_category.get(s.category, 0.0) + float(p)
    category = max(by_category, key=by_category.__getitem__)
    best = max((i for i, s in enumerate(subs) if s.category == category), key=lambda i: p_sub[i])

    p_season = head("seasons", cfg.seasons)
    keep = cfg.thresholds.season_relative * float(p_season.max())
    season = [s.label for s, p in zip(cfg.seasons, p_season, strict=True) if p >= keep]

    p_pattern = head("patterns", cfg.patterns)
    p_material = head("materials", cfg.materials)
    p_formal = head("formality", cfg.formality)
    formality = float(np.dot(p_formal, [f.value for f in cfg.formality]))

    return Attributes(
        category=category,
        subcategory=subs[best].label,
        local_tag=subs[best].local_tag,
        confidence=round(min(by_category[category], 1.0), 4),
        season=season,
        pattern=cfg.patterns[int(np.argmax(p_pattern))].label,
        material=cfg.materials[int(np.argmax(p_material))].label,
        formality=round(min(max(formality, 0.0), 1.0), 3),
    )
