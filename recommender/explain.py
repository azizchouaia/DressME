"""Say why an outfit was chosen, using only scores and the request."""

from __future__ import annotations

from recommender.engine import Conditions, Outfit


def explain(outfit: Outfit, conditions: Conditions, taste_ready: bool, from_photo: bool) -> str:
    if not outfit.pieces:
        return outfit.reason
    lines = [outfit.reason, ""]
    situation = conditions.text()
    if situation:
        lines.append(f"The request was {situation}.")
    if from_photo:
        lines.append("The photo fixes one piece. The other slots were filled from the wardrobe around it.")
    if taste_ready:
        lines.append(
            "Your saved likes sit in one or more tastes. A newer opinion counts more than an old one. "
            "One extra suggestion stays close to those tastes, so we can see if you want to move that way."
        )
    else:
        lines.append("There is no taste profile yet, so nothing here is based on a past like.")
    lines.append("Each piece:")
    for item in outfit.pieces:
        why = _slot_why(item.piece.slot, conditions, from_photo and item.piece.id == "upload")
        lines.append(f"- {item.piece.name} ({item.piece.slot}, score {item.score:.2f}). {why}")
    lines.append(f"The pieces agree with each other at {outfit.compatibility:.2f} in the fashion embedding space.")
    return "\n".join(lines)


def _slot_why(slot: str, conditions: Conditions, is_photo: bool) -> str:
    if is_photo:
        return "This is the piece in the photo, so the outfit is built around it."
    if slot == "outer" and conditions.wants_outer():
        return "A layer is included because the weather or season is cold or wet."
    if slot == "top":
        return "This is the closest top to the request and to your taste."
    if slot == "bottom":
        return "This bottom both scores well and sits near the pieces already chosen."
    if slot == "shoes":
        return "These shoes close the outfit without breaking the size or budget filter."
    return "It passed the filters and scored next to the rest of the outfit."
