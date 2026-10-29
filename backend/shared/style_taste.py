"""The taste learnt by M5 (BO4, Amine) for a user: 512-d FashionCLIP vector, or None.

Used by the outfit makers (BO1 / BO2 stylist) so M2's `style_match` follows what the user swiped,
as M5's INTEGRATION.md asks: read the taste from M5, never recompute it.
"""

from __future__ import annotations

import logging

log = logging.getLogger("dressme.style_taste")


def taste_vector(user_id: str | None) -> list[float] | None:
    if not user_id or str(user_id).startswith("demo_"):
        return None
    try:
        from modules.m05_style_profile import service
        from shared.user_wardrobe import _run

        p = _run(service.profile(user_id))
        v = getattr(p, "taste_vector", None) if not isinstance(p, dict) else p.get("taste_vector")
        return [float(x) for x in v] if v else None
    except Exception as e:  # noqa: BLE001 - no profile yet / M5 store down: outfits without the taste
        log.info("no M5 taste for %s: %s", user_id, e)
        return None
