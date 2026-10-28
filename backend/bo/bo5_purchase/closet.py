"""'My closet': a real wardrobe built from your own photos (user id: usr_me).

Stored in ml/data/bo5/my_closet/ (closet.json + images/). Photos stay on your PC, not in git.
Each item keeps what the AI saw ("ai") and what you corrected, so corrections become training data.
"""

import json
import uuid
from pathlib import Path

from modules.m06_smartbuy import synthetic as syn

DIR = Path(__file__).resolve().parent.parent.parent.parent / "ml" / "data" / "bo5" / "my_closet"
IMAGES = DIR / "images"
FILE = DIR / "closet.json"
USER = "usr_me"


def load() -> dict:
    if FILE.exists():
        return json.loads(FILE.read_text(encoding="utf-8"))
    return {"user_id": USER, "gaps": [], "items": []}


def save(w: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    FILE.write_text(json.dumps(w, indent=1), encoding="utf-8")


def _item(sub: str, col: str) -> dict:
    return {"label": syn.label(f"{col} {sub}"), "category": syn.TYPES[sub][0], "subcategory": sub,
            "colour": col, "embedding": syn.embed(sub, col)}


def add(image_bytes: bytes, suffix: str, ai: dict) -> dict:
    w = load()
    IMAGES.mkdir(parents=True, exist_ok=True)
    iid = f"me_{uuid.uuid4().hex[:8]}"
    name = f"{iid}{suffix.lower() if suffix else '.jpg'}"
    (IMAGES / name).write_bytes(image_bytes)
    it = {"id": iid, **_item(ai["subcategory"], ai["colour"]), "image": name,
          "ai": {"subcategory": ai["subcategory"], "colour": ai["colour"], "confidence": ai["confidence"]},
          "corrected": False, "checked": False}
    w["items"].append(it)
    save(w)
    return it


def correct(item_id: str, sub: str, col: str) -> dict:
    w = load()
    for it in w["items"]:
        if it["id"] == item_id:
            ai = it.get("ai")
            it.update(_item(sub, col))
            it["corrected"] = bool(ai) and (ai["subcategory"], ai["colour"]) != (sub, col)
            it["checked"] = True  # user confirmed the tags
            save(w)
            return it
    raise KeyError(item_id)


def remove(item_id: str) -> None:
    w = load()
    keep = [i for i in w["items"] if i["id"] != item_id]
    for i in w["items"]:
        if i["id"] == item_id and i.get("image") and (IMAGES / i["image"]).exists():
            (IMAGES / i["image"]).unlink()
    w["items"] = keep
    save(w)


def set_gaps(gaps: list[str]) -> dict:
    w = load()
    w["gaps"] = [g.strip().lower() for g in gaps if g.strip()]
    save(w)
    return w
