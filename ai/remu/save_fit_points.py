"""Save the body vertices the clothes model chose. Texture stays with ReMU."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))
sys.path.insert(0, str(ROOT / "ai" / "remu"))

from garment_job import _joint_weights
from skin_garments import body_skin

BODY = ROOT / "avatar_studio" / "web" / "users" / "test-it.glb"
EDGES = ROOT / "avatar_studio" / "web" / "garments" / "saved" / "samples" / "vision-edges.json"
OUT = ROOT / "avatar_studio" / "web" / "garments" / "saved" / "fit_points"


def chosen(edges: dict):
    positions, joints, weights, names, parents, world = body_skin(BODY)
    labels = [str(name or "").lower() for name in names]
    feet_y = float(positions[:, 1].min())
    span = float(positions[:, 1].max()) - feet_y
    shirt_hem = feet_y + edges["shirt_hem"] * span
    pants_hem = feet_y + edges["pants_hem"] * span
    pants_top = feet_y + edges["pants_top"] * span

    torso = {"spine1", "spine2", "spine3", "left_collar", "right_collar", "left_shoulder", "right_shoulder"}
    blocked = {
        "neck", "head", "jaw", "left_eye_smplhf", "right_eye_smplhf",
        "left_knee", "right_knee", "left_ankle", "right_ankle", "left_foot", "right_foot",
        "left_wrist", "right_wrist",
    }
    if edges["long_sleeve"]:
        torso |= {"left_elbow", "right_elbow"}
    else:
        blocked |= {"left_elbow", "right_elbow"}
    torso_w = _joint_weights(joints, weights, labels, torso)
    blocked_w = _joint_weights(joints, weights, labels, blocked)
    pelvis_w = _joint_weights(joints, weights, labels, {"pelvis"})
    hip_w = _joint_weights(joints, weights, labels, {"left_hip", "right_hip"})
    shirt = np.flatnonzero(
        (positions[:, 1] > shirt_hem - 0.02)
        & (blocked_w < 0.42)
        & (
            ((torso_w >= 0.35) & (blocked_w < 0.42))
            | ((pelvis_w >= 0.12) & (hip_w < 0.55))
            | ((hip_w >= 0.2) & (positions[:, 1] > min(shirt_hem, pants_top) - 0.02))
        )
    )
    legs = {"left_hip", "right_hip", "left_knee", "right_knee"}
    if pants_hem < feet_y + 0.16 * span:
        legs |= {"left_ankle", "right_ankle"}
    leg_w = _joint_weights(joints, weights, labels, legs)
    foot_w = _joint_weights(joints, weights, labels, {"left_foot", "right_foot"})
    pants = np.flatnonzero(
        (leg_w >= 0.35)
        & (foot_w < 0.25)
        & (positions[:, 1] > pants_hem)
        & (positions[:, 1] < max(shirt_hem, pants_top) + 0.03)
    )
    return {
        "shirt": shirt.astype(np.int64),
        "pants": pants.astype(np.int64),
        "shirt_hem": shirt_hem,
        "pants_hem": pants_hem,
        "pants_top": pants_top,
    }


def main() -> None:
    edges = json.loads(EDGES.read_text(encoding="utf-8"))
    picked = chosen(edges)
    OUT.mkdir(parents=True, exist_ok=True)
    np.save(OUT / "shirt.npy", picked["shirt"])
    np.save(OUT / "pants.npy", picked["pants"])
    record = {
        "body": "/users/test-it.glb",
        "source": "segformer clothes model on the full-body photo",
        "shirt_vertices": int(len(picked["shirt"])),
        "pants_vertices": int(len(picked["pants"])),
        "shirt_hem": round(float(picked["shirt_hem"]), 4),
        "pants_hem": round(float(picked["pants_hem"]), 4),
        "pants_top": round(float(picked["pants_top"]), 4),
        "long_sleeve": bool(edges["long_sleeve"]),
        "owns": "where the cloth sits on this avatar",
        "remu_owns": "cloth shape, edges, texture, and how loose it is",
    }
    (OUT / "fit.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
