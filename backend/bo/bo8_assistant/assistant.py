"""BO8 personal assistant. It calls M8 for parsing, ranking, explanation, and shops."""

from modules.m08_llm_layer.service import chat, explain, parse, recommend


def reply(user_id: str, message: str, pieces: list[dict], events: list[dict] | None = None) -> dict:
    """One turn. `pieces` carry the vectors produced upstream (FashionCLIP)."""

    return chat(
        {
            "user_id": user_id,
            "payload": {"message": message, "pieces": pieces, "events": events or []},
        }
    )["result"]


__all__ = ["reply", "parse", "explain", "recommend"]
