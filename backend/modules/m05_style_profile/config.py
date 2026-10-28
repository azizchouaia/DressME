"""Loads config.yaml, styles.json and reference_looks.json. Env: M05_RANKING, M05_STORE, M05_AGENT_*."""

import hashlib
import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

MODULE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = MODULE_DIR / "config.yaml"


class BanditConfig(BaseModel):
    v: float = Field(gt=0)
    prior_strength: float = Field(gt=0)
    batch_size: int = Field(ge=1)
    onboarding_cards: int = Field(ge=1)


class RocchioConfig(BaseModel):
    reject_weight: float = Field(ge=0)
    wish_weight: float = Field(ge=0)
    explore_cards: int = Field(ge=0)
    negative_reward: float


class ContextConfig(BaseModel):
    occasions: list[str]
    baseline_occasion: str
    aliases: dict[str, str] = {}
    temp_center: float
    temp_scale: float = Field(gt=0)

    def all_occasions(self) -> list[str]:
        return [*self.occasions, self.baseline_occasion, *self.aliases]

    def canonical(self, occasion: str) -> str:
        return self.aliases.get(occasion, occasion)


class PriorConfig(BaseModel):
    want_more: float
    want_less: float
    taste_sim: float


class WarmthConfig(BaseModel):
    seasons: dict[str, float]
    default: float
    subcategory_bonus: dict[str, float] = {}
    material_bonus: dict[str, float] = {}


class M02Config(BaseModel):
    source: str = "mock"
    n_candidates: int
    hot_temp: float
    warm_item: float
    outer_below: float
    sized_categories: list[str]


class M03Config(BaseModel):
    source: str = "mock"
    default_novelty: float
    novelty_full_after_days: int


class AgentConfig(BaseModel):
    """Style coach agent (agent/). Env overrides: M05_AGENT_PROVIDER, M05_AGENT_MODEL, M05_AGENT_BASE_URL."""

    provider: str = "ollama"  # ollama | shared (backend/shared/llm.py: LLM_PROVIDER / LLM_MODEL)
    model: str = "qwen3:4b-instruct"
    base_url: str = "http://localhost:11434"
    temperature: float = Field(default=0.2, ge=0, le=2)
    num_ctx: int = Field(default=6144, ge=1024)
    history_messages: int = Field(default=12, ge=2)
    max_steps: int = Field(default=16, ge=4)
    recommend_k: int = Field(default=3, ge=1, le=10)


class M05Config(BaseModel):
    styles_file: str
    reference_looks_file: str
    style_mix_factor: float = Field(gt=0)
    ranking: Literal["rocchio", "bandit"] = "rocchio"
    rocchio: RocchioConfig
    bandit: BanditConfig
    onboarding_contexts: list[dict]
    taste_lr: float = Field(ge=0, le=1)
    positive_reward: float
    rewards: dict[str, float]
    source_weights: dict[str, float]
    context: ContextConfig
    prior: PriorConfig
    warmth: WarmthConfig
    m02: M02Config
    m03: M03Config
    storage: str = "auto"
    chat_mix_step: float = Field(default=0.1, ge=0, le=1)
    agent: AgentConfig = AgentConfig()


@lru_cache
def get_config() -> M05Config:
    cfg = M05Config.model_validate(yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")))
    if ranking := os.environ.get("M05_RANKING"):
        cfg.ranking = ranking.strip().lower()
    if store := os.environ.get("M05_STORE"):
        cfg.storage = store.strip().lower()
    for key in ("provider", "model", "base_url"):
        if value := os.environ.get(f"M05_AGENT_{key.upper()}"):
            setattr(cfg.agent, key, value.strip())
    return cfg


# --- style list -------------------------------------------------------------------------------------


class Family(BaseModel):
    label: str
    colour: str = "#888888"


class StyleDef(BaseModel):
    id: str
    family: str
    label: str | None = None
    description: str
    vector_source: str = "text"  # text | images
    examples: list[str] = []  # image URLs / data URLs when vector_source = images


class StyleList(BaseModel):
    families: dict[str, Family]
    styles: list[StyleDef] = Field(min_length=2)
    version: str = ""

    @model_validator(mode="after")
    def _check(self):
        ids = self.ids
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate style ids")
        unknown = {s.family for s in self.styles} - set(self.families)
        if unknown:
            raise ValueError(f"styles use unknown families: {sorted(unknown)}")
        return self

    @property
    def ids(self) -> list[str]:
        return [s.id for s in self.styles]

    def family_of(self, style_id: str) -> str:
        return next(s.family for s in self.styles if s.id == style_id)


def load_styles(path: Path | None = None) -> StyleList:
    """Reads the style list. Its version is a hash of the file: any edit invalidates the stored mixes."""
    path = path or MODULE_DIR / get_config().styles_file
    raw = path.read_bytes()
    data = yaml.safe_load(raw.decode("utf-8"))  # JSON is valid YAML
    data.pop("_comment", None)
    return StyleList.model_validate({**data, "version": hashlib.sha1(raw).hexdigest()[:12]})


class LookDef(BaseModel):
    id: str
    style_id: str
    title: str
    description: str
    primary: bool = False
    formality: float = Field(default=0.5, ge=0, le=1)
    warmth: float = Field(default=0.5, ge=0, le=1)
    image_url: str | None = None
    vector_source: str = "text"  # text | image (FashionCLIP embedding of image_url, through M1)
    art: dict | None = None  # the outfit drawn on the card when there is no photo (looks_svg.py)


def load_reference_looks(path: Path | None = None) -> list[LookDef]:
    path = path or MODULE_DIR / get_config().reference_looks_file
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return [LookDef.model_validate(x) for x in data["looks"]]
