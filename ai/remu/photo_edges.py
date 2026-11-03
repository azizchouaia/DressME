"""Read clothing edges from a person photo and cloth from a garment photo."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

SAMPLES = Path(__file__).resolve().parents[2] / "avatar_studio" / "web" / "garments" / "saved" / "samples"
PERSON = SAMPLES / "person-a.jpg"
GARMENT = SAMPLES / "garment-tee.jpg"


def _person_edges() -> dict:
    image = np.asarray(Image.open(PERSON).convert("RGB")).astype(np.float32)
    height, width, _ = image.shape
    column = image[:, width // 2 - 25:width // 2 + 25].mean(axis=(1, 2))
    shirt_rows = np.nonzero(column > 155)[0]
    splits = np.nonzero(np.diff(shirt_rows) > 12)[0]
    groups = [group for group in np.split(shirt_rows, splits + 1) if len(group) > 30]
    shirt = max(groups, key=len)
    shirt_top, shirt_bottom = int(shirt[0]), int(shirt[-1])
    shirt_span = max(shirt_bottom - shirt_top, 1)
    bright = image[shirt_top:shirt_bottom].mean(axis=2) > 150
    cols = np.nonzero(bright.any(axis=0))[0]
    left, right = int(cols[0]), int(cols[-1])
    thigh = int(left + (right - left) * 0.28)
    below = column[shirt_bottom:min(height, shirt_bottom + shirt_span * 2)]
    end = 0
    light = 0
    for index, value in enumerate(below):
        if value < 100:
            end = index
            light = 0
        else:
            light += 1
            if light > 18 and end > 30:
                break
    shorts_bottom = shirt_bottom + int(end)
    above = np.nonzero(column[:shirt_top] < 110)[0]
    near = above[above > shirt_top - 500] if len(above) else above
    head = int(near[0]) if len(near) else max(0, shirt_top - shirt_span)
    feet = min(height - 1, shirt_bottom + int(shirt_span * 3.1))
    body = max(feet - head, 1)

    def frac_from_feet(row: int) -> float:
        return float(np.clip((feet - row) / body, 0.05, 0.92))

    edges = {
        "shirt_hem": frac_from_feet(shirt_bottom),
        "neckline": frac_from_feet(shirt_top),
        "shorts_hem": frac_from_feet(shorts_bottom),
        "waist": frac_from_feet(shirt_bottom),
    }
    preview = Image.open(PERSON).convert("RGB")
    draw = ImageDraw.Draw(preview)
    for name, row in (("neck", shirt_top), ("hem", shirt_bottom), ("shorts", shorts_bottom), ("feet", feet), ("head", head)):
        draw.line((0, row, width, row), fill=(220, 40, 40), width=4)
        draw.text((12, max(0, row - 18)), name, fill=(220, 40, 40))
    preview.save(SAMPLES / "edges.png")
    (SAMPLES / "edges.json").write_text(json.dumps(edges, indent=2), encoding="utf-8")
    print(json.dumps(edges, indent=2))
    print("rows head", head, "neck", shirt_top, "hem", shirt_bottom, "shorts", shorts_bottom, "feet", feet)
    return edges


def _garment_cloth() -> None:
    image = np.asarray(Image.open(GARMENT).convert("RGB"))
    height, width, _ = image.shape
    # The print is the dark disc on the grey shirt, above the jeans.
    torso = image[int(height * 0.45):int(height * 0.70), int(width * 0.42):int(width * 0.78)]
    gray = torso.mean(axis=2)
    ink = gray < 80
    ys, xs = np.nonzero(ink)
    if len(xs) < 30:
        raise RuntimeError("The garment photo has no dark print.")
    pad = 16
    y0, y1 = max(0, int(ys.min()) - pad), min(torso.shape[0], int(ys.max()) + pad)
    x0, x1 = max(0, int(xs.min()) - pad), min(torso.shape[1], int(xs.max()) + pad)
    crop = torso[y0:y1, x0:x1]
    crop_gray = crop.mean(axis=2)
    shirt = crop[(crop_gray > 90) & (crop_gray < 170)]
    color = np.median(shirt, axis=0) if len(shirt) else np.array([150, 148, 146])
    cotton = np.array(color, dtype=np.uint8)
    isolated = np.broadcast_to(cotton, crop.shape).copy()
    isolated[crop_gray < 95] = crop[crop_gray < 95]
    Image.fromarray(isolated).save(SAMPLES / "print.png")
    jeans = image[int(height * 0.78):int(height * 0.95), int(width * 0.40):int(width * 0.75)]
    Image.fromarray(jeans).save(SAMPLES / "jeans_crop.png")
    print("shirt color", [int(v) for v in color])


def _apply(edges: dict) -> None:
    import sys

    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root / "ai"))
    sys.path.insert(0, str(root / "ai" / "remu"))
    from garment_job import WEB, _cut_cloth, _joint_weights
    from skin_garments import body_skin
    from texture_samples import _cotton, _pack
    import numpy as np
    from PIL import Image

    body = root / "avatar_studio" / "web" / "users" / "test-it.glb"
    positions, joints, weights, names, parents, world = body_skin(body)
    labels = [str(name or "").lower() for name in names]
    head_y = float(positions[:, 1].max())
    feet_y = float(positions[:, 1].min())
    span = head_y - feet_y
    shirt_hem = feet_y + edges["shirt_hem"] * span
    shorts_hem = feet_y + edges["shorts_hem"] * span
    neckline = feet_y + edges["neckline"] * span
    print("avatar shirt hem", round(shirt_hem, 3), "shorts hem", round(shorts_hem, 3), "neckline", round(neckline, 3))

    torso = {"spine1", "spine2", "spine3", "left_collar", "right_collar", "left_shoulder", "right_shoulder"}
    blocked = {
        "neck", "head", "jaw", "left_eye_smplhf", "right_eye_smplhf",
        "left_hip", "right_hip", "left_knee", "right_knee",
        "left_ankle", "right_ankle", "left_foot", "right_foot",
        "left_elbow", "right_elbow", "left_wrist", "right_wrist",
    }
    torso_w = _joint_weights(joints, weights, labels, torso)
    blocked_w = _joint_weights(joints, weights, labels, blocked)
    pelvis_w = _joint_weights(joints, weights, labels, {"pelvis"})
    belly = (pelvis_w >= 0.12) & (positions[:, 1] > shirt_hem - 0.1) & (blocked_w < 0.35)
    shirt = np.flatnonzero(
        (((torso_w >= 0.4) & (blocked_w < 0.42)) | belly)
        & (positions[:, 1] > shirt_hem - 0.1)
    )
    out = root / "avatar_studio" / "web" / "garments"
    _cut_cloth(body, shirt, out / "fitted.glb", [0.58, 0.52, 0.48, 1], 0.014)

    legs = {"left_hip", "right_hip", "left_knee", "right_knee"}
    leg_w = _joint_weights(joints, weights, labels, legs)
    foot_w = _joint_weights(joints, weights, labels, {"left_foot", "right_foot", "left_ankle", "right_ankle"})
    shorts = np.flatnonzero(
        (leg_w >= 0.35)
        & (foot_w < 0.25)
        & (positions[:, 1] > shorts_hem)
        & (positions[:, 1] < shirt_hem + 0.03)
    )
    print("shorts verts", len(shorts), "y", round(float(positions[shorts, 1].min()), 3), round(float(positions[shorts, 1].max()), 3))
    _cut_cloth(body, shorts, out / "pants.glb", [0.25, 0.32, 0.42, 1], 0.008, min_faces=40)

    graphic = Image.open(SAMPLES / "print.png").convert("RGB")
    graphic_px = np.asarray(graphic)
    ink = graphic_px.mean(axis=2) < 90
    rows = np.nonzero(ink.any(axis=1))[0]
    cols = np.nonzero(ink.any(axis=0))[0]
    if len(rows):
        graphic = graphic.crop((int(cols[0]), int(rows[len(rows) // 5]), int(cols[-1]), int(rows[-1])))
    color = (146, 130, 118)
    albedo = _cotton(color, 1024)
    stamp = graphic.resize((280, 280), Image.Resampling.LANCZOS)
    front = Image.fromarray(albedo[:, :512])
    front.paste(stamp, ((512 - stamp.width) // 2, 120))
    albedo[:, :512] = np.asarray(front)
    shirt_albedo = Image.fromarray(albedo)
    shirt_albedo.save(SAMPLES / "shirt_albedo.png")
    denim = _cotton((48, 72, 108), 1024)
    _pack(out / "fitted.glb", shirt_albedo, 0)
    _pack(out / "pants.glb", Image.fromarray(denim), 0)
    saved, *_ = body_skin(out / "pants.glb")
    print("saved shorts", len(saved), round(float(saved[:, 1].min()), 3), round(float(saved[:, 1].max()), 3))
    print("wore the measured shirt and shorts")


if __name__ == "__main__":
    edges = _person_edges()
    _garment_cloth()
    _apply(edges)
