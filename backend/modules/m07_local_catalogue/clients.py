"""Calls to other shared modules. Rule: call their API (or mock), never re-implement them."""

import logging

log = logging.getLogger("m07.clients")


def style_vector_from_m5(user_id: str | None, vector_id: str) -> list[float] | None:
    """Resolve a style vector id ("vec_u042", as in the architecture doc) through M5 Style profile.

    Uses M5's mock or service the same way M5's router does. Returns None while M5 does not expose
    the vector yet; the caller then ranks without the style part and says so.
    """
    try:
        from modules.m05_style_profile import mock, service
        from shared.config import settings

        impl = mock if getattr(settings, "use_mocks", True) else service
        answer = impl.profile({"user_id": user_id, "payload": {"style_vector_id": vector_id}})
    except Exception as exc:  # M5 missing, not implemented yet, or failing: M7 must still answer
        log.warning("M5 style vector %s unavailable: %s", vector_id, exc)
        return None
    vector = (answer.get("result") or {}).get("style_vector")
    if isinstance(vector, list) and vector and all(isinstance(v, int | float) for v in vector):
        return [float(v) for v in vector]
    return None
