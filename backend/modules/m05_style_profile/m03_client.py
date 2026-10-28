"""Bridge to M3 (wear log, owner BO1/BO2). M3 is not merged yet: the mock is used (config m03.source).

mock        : novelty = default_novelty (0.5) for every outfit
item_fields : novelty from M1's last_worn (0 = worn today .. 1 = not worn for novelty_full_after_days)
"""

import datetime as dt

from .config import get_config


def novelty(items: list, today: dt.date | None = None) -> float:
    """Novelty of an outfit = novelty of its most recently worn piece."""
    cfg = get_config().m03
    if cfg.source != "item_fields":
        return cfg.default_novelty
    today = today or dt.date.today()
    values = []
    for item in items:
        if item.last_worn is None:
            values.append(1.0)
        else:
            values.append(min(1.0, max(0, (today - item.last_worn).days) / cfg.novelty_full_after_days))
    return round(min(values), 3) if values else cfg.default_novelty


async def record_worn(user_id: str, item_ids: list[str]) -> None:
    """A 'worn' feedback received by M5. The real M3 owns the wear log: nothing to do in the mock."""
    return None
