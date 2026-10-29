"""Per-item attributes M5 needs on top of M1's: warmth (computed here), formality (M1, default 0.5)."""

from .config import WarmthConfig, get_config


def warmth(item, cfg: WarmthConfig | None = None) -> float:
    """0 (summer) .. 1 (winter): mean of the item's seasons, plus subcategory / material bonuses."""
    cfg = cfg or get_config().warmth
    seasons = [cfg.seasons[s] for s in (item.season or []) if s in cfg.seasons]
    w = sum(seasons) / len(seasons) if seasons else cfg.default
    w += cfg.subcategory_bonus.get((item.subcategory or "").lower(), 0.0)
    w += cfg.material_bonus.get((item.material or "").lower(), 0.0)
    return round(min(max(w, 0.0), 1.0), 3)


def formality(item) -> float:
    return 0.5 if item.formality is None else float(item.formality)


def normalise_size(size: str | None) -> str | None:
    return None if not size else size.strip().upper().replace(" ", "")
