"""M9 status for the faceless avatar. The meshes stay on the machine that built them.

See ARCHITECTURE.md in this folder. This endpoint does not render a frame. It
returns the manifest the viewer and the cloth pipeline already use.
"""

from __future__ import annotations

import json
from pathlib import Path

_MANIFEST = json.loads(Path(__file__).with_name("manifest.json").read_text(encoding="utf-8"))


def render(req: dict) -> dict:
    payload = req.get("payload") or {}
    return {
        "result": {
            "user_id": req.get("user_id"),
            "pose": payload.get("pose") or "standing",
            "garments": [item["id"] for item in _MANIFEST["garments"]],
            "body": _MANIFEST["body"]["shown"],
            "manifest": _MANIFEST,
            "doc": "backend/modules/m09_avatar_3d/ARCHITECTURE.md",
        },
        "mocked": False,
    }
