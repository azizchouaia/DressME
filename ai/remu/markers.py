"""Name the garment with the four markers, then stop. ReMU does the cloth."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from vision_fit import (
    FACE,
    HAIR,
    HAT,
    LEFT_ARM,
    LEFT_LEG,
    LEFT_SHOE,
    PANTS,
    RIGHT_ARM,
    RIGHT_LEG,
    RIGHT_SHOE,
    SKIRT,
    UPPER,
    _person,
    _rows,
    _segment,
)


def classify(path: Path) -> dict:
    image, labels = _segment(path)
    edges = _person(image, labels)
    top = "long_sleeves" if edges["sleeve_cover"] >= 0.5 else "short_sleeves"
    bottom = "pants" if edges["pants_hem"] < 0.2 else "shorts"
    head = len(_rows(np.isin(labels, (HAT, HAIR, FACE)))) > 0
    shoes = len(_rows(np.isin(labels, (LEFT_SHOE, RIGHT_SHOE)))) > 0
    raised = 0
    shirt_top = int(np.nonzero((labels == UPPER).any(axis=1))[0][0])
    for arm in (LEFT_ARM, RIGHT_ARM):
        rows = _rows(labels == arm)
        if len(rows) > 8 and int(rows[0]) < shirt_top - 20:
            raised += 1
    ready = head and shoes and raised == 0 and int((labels == UPPER).sum()) > 200
    reason = "The front photo shows the head, the clothes, and the feet, with the arms beside the body."
    if not ready:
        reason = "ReMU needs the whole person, feet included, and the arms beside the clothes."
    return {
        "top": top,
        "bottom": bottom,
        "sleeve_cover": edges["sleeve_cover"],
        "shirt_hem": edges["shirt_hem"],
        "pants_hem": edges["pants_hem"],
        "pants_top": edges["pants_top"],
        "neckline": edges["neckline"],
        "long_sleeve": top == "long_sleeves",
        "ready_for_remu": ready,
        "reason": reason,
    }


def main() -> None:
    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    record = classify(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record))
    if not record["ready_for_remu"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
