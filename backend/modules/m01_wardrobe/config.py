"""Loads config.yaml once. A few values can be overridden by environment variables (M01_*)."""

import os
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from shared.schemas import GarmentCategory

MODULE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = MODULE_DIR / "config.yaml"


class Label(BaseModel):
    label: str
    prompt: str | None = None

    def text(self, template: str) -> str:
        return template.format(label=self.prompt or self.label)


class SubcategoryLabel(Label):
    category: GarmentCategory
    local_tag: str | None = None


class FormalityLabel(Label):
    value: float


class Models(BaseModel):
    clip: str
    rembg: str
    rembg_fallback: str
    device: str = "cpu"


class Thresholds(BaseModel):
    duplicate: float
    similar: float
    confidence: float
    season_relative: float


class DonationLLM(BaseModel):
    model: str = "qwen3:4b-instruct"
    base_url: str = "http://localhost:11434"
    temperature: float = Field(default=0.2, ge=0, le=2)
    timeout_s: float = Field(default=60, gt=0)


class Donation(BaseModel):
    places_file: str = "donation_places.json"
    max_suggestions: int = Field(default=3, ge=1, le=5)
    llm: DonationLLM = DonationLLM()


class M01Config(BaseModel):
    models: Models
    thresholds: Thresholds
    prompt_template: str
    logit_scales: dict[str, float] = {}     # head -> scale; missing = the model's own scale
    subcategories: list[SubcategoryLabel]
    seasons: list[Label]
    patterns: list[Label]
    materials: list[Label]
    formality: list[FormalityLabel]
    palette: dict[str, str]
    donation: Donation = Donation()


@lru_cache
def get_config() -> M01Config:
    cfg = M01Config.model_validate(yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")))
    if device := os.environ.get("M01_DEVICE"):
        cfg.models.device = device
    if model := os.environ.get("M01_DONATION_MODEL"):
        cfg.donation.llm.model = model
    return cfg


def data_dir() -> Path:
    """Local image store (git-ignored). Read at call time so tests can redirect it."""
    return Path(os.environ.get("M01_DATA_DIR") or MODULE_DIR / "data")


def use_mocks(global_default: bool) -> bool:
    """M01_USE_MOCKS (true/false) overrides the global USE_MOCKS for M1 only.

    This lets M1 run for real while the other modules, whose service.py is not ready, keep their mocks.
    """
    override = os.environ.get("M01_USE_MOCKS")
    if override is None or not override.strip():
        return global_default
    return override.strip().lower() not in ("0", "false", "no", "off")


def storage_backend() -> str:
    """`local` (default, served by GET /m01/media/...) or `s3` (shared/storage.py)."""
    return os.environ.get("M01_STORAGE", "local").lower()
