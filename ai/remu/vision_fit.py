"""Skin-fit shirt and bottoms from a clothes-segmentation model.

The full-body photo sets the hem, the sleeve, and the cloth color.
A second photo of a printed shirt sets the graphic box on that shirt.
Shoes and hats are left out.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "avatar_studio" / "web" / "garments" / "saved" / "samples"
PERSON = SAMPLES / "vision-shorts.jpg"
PRINT = SAMPLES / "vision-print.jpg"
BODY = ROOT / "avatar_studio" / "web" / "users" / "test-it.glb"
GARMENTS = ROOT / "avatar_studio" / "web" / "garments"

UPPER, PANTS, SKIRT = 4, 6, 5
HAT, HAIR, FACE = 1, 2, 11
LEFT_SHOE, RIGHT_SHOE = 9, 10
LEFT_LEG, RIGHT_LEG = 12, 13
LEFT_ARM, RIGHT_ARM = 14, 15


def _segment(path: Path) -> tuple[np.ndarray, np.ndarray]:
    image = Image.open(path).convert("RGB")
    cache = path.with_suffix(".labels.npz")
    if cache.exists() and cache.stat().st_mtime >= path.stat().st_mtime:
        return np.asarray(image), np.load(cache)["labels"]
    import torch
    from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor
    processor = SegformerImageProcessor.from_pretrained("mattmdjaga/segformer_b2_clothes")
    model = SegformerForSemanticSegmentation.from_pretrained("mattmdjaga/segformer_b2_clothes")
    model.eval()
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits
    size = (image.height, image.width)
    labels = torch.nn.functional.interpolate(logits, size=size, mode="bilinear", align_corners=False)
    parsed = labels.argmax(dim=1)[0].cpu().numpy().astype(np.uint8)
    np.savez_compressed(cache, labels=parsed)
    return np.asarray(image), parsed


def _rows(mask: np.ndarray) -> np.ndarray:
    return np.nonzero(mask.any(axis=1))[0]


def _span(mask: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        raise RuntimeError("The clothes model found no region.")
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def _largest(mask: np.ndarray) -> np.ndarray:
    from scipy import ndimage

    labeled, count = ndimage.label(mask)
    if count == 0:
        return mask
    sizes = ndimage.sum(mask, labeled, range(1, count + 1))
    return labeled == (int(np.argmax(sizes)) + 1)


def _overlay(image: np.ndarray, labels: np.ndarray, name: str) -> None:
    tint = np.zeros_like(image)
    tint[labels == UPPER] = (40, 120, 220)
    tint[np.isin(labels, (PANTS, SKIRT))] = (40, 170, 80)
    tint[np.isin(labels, (LEFT_ARM, RIGHT_ARM, LEFT_LEG, RIGHT_LEG))] = (220, 170, 60)
    mixed = (image.astype(np.float32) * 0.55 + tint.astype(np.float32) * 0.45).astype(np.uint8)
    Image.fromarray(mixed).save(SAMPLES / name)


def _frac(row: int, head: int, feet: int) -> float:
    return float(np.clip((feet - row) / max(feet - head, 1), 0.04, 0.96))


def _person(image: np.ndarray, labels: np.ndarray) -> dict:
    upper = labels == UPPER
    lower = np.isin(labels, (PANTS, SKIRT))
    if upper.sum() < 200 or lower.sum() < 200:
        raise RuntimeError("The full-body photo has no shirt and bottoms.")
    head_rows = _rows(np.isin(labels, (HAT, HAIR, FACE)))
    feet_rows = _rows(np.isin(labels, (LEFT_SHOE, RIGHT_SHOE, LEFT_LEG, RIGHT_LEG, PANTS, SKIRT)))
    head = int(head_rows[0]) if len(head_rows) else 0
    feet = int(feet_rows[-1]) if len(feet_rows) else image.shape[0] - 1
    x0, y0, x1, y1 = _span(upper)
    center = upper[:, x0 + (x1 - x0) // 3:x0 + 2 * (x1 - x0) // 3]
    shirt_rows = _rows(center)
    shirt_top, shirt_bottom = int(shirt_rows[0]), int(shirt_rows[-1])
    low_x0, low_y0, low_x1, low_y1 = _span(lower)
    mid = lower[:, low_x0 + (low_x1 - low_x0) // 4:low_x0 + 3 * (low_x1 - low_x0) // 4]
    low_rows = _rows(mid)
    pants_top, pants_bottom = int(low_rows[0]), int(low_rows[-1])

    sleeve = _sleeve(labels, x0, x1, shirt_top)
    shirt_px = image[upper]
    far = np.linalg.norm(shirt_px.astype(np.float32) - np.median(shirt_px, axis=0), axis=1)
    cloth = shirt_px[far < np.percentile(far, 70)]
    shirt_color = np.median(cloth, axis=0)
    pants_color = np.median(image[lower], axis=0)

    preview = Image.fromarray(image)
    draw = ImageDraw.Draw(preview)
    for name, row in (("neck", shirt_top), ("hem", shirt_bottom), ("shorts", pants_bottom)):
        draw.line((0, row, image.shape[1], row), fill=(220, 40, 40), width=4)
        draw.text((16, max(0, row - 18)), name, fill=(220, 40, 40))
    preview.save(SAMPLES / "vision-edges.png")

    edges = {
        "shirt_hem": _frac(shirt_bottom, head, feet),
        "neckline": _frac(shirt_top, head, feet),
        "pants_hem": _frac(pants_bottom, head, feet),
        "pants_top": _frac(pants_top, head, feet),
        "long_sleeve": sleeve > 0.62,
        "sleeve_cover": sleeve,
        "shirt_color": [int(v) for v in shirt_color],
        "pants_color": [int(v) for v in pants_color],
    }
    print(json.dumps(edges, indent=2))
    return edges


def _sleeve(labels: np.ndarray, x0: int, x1: int, shirt_top: int) -> float:
    """How far the cloth goes down the hanging arm. 0 is a cap sleeve, 1 reaches the hand."""
    from scipy import ndimage

    covers = []
    for arm in (LEFT_ARM, RIGHT_ARM):
        skin = labels == arm
        skin_rows = _rows(skin)
        if len(skin_rows) < 8 or int(skin_rows[0]) < shirt_top - 20:
            continue
        contact = (labels == UPPER) & ndimage.binary_dilation(skin, iterations=6)
        contact_rows = _rows(contact)
        if len(contact_rows) < 4:
            continue
        shoulder = int(skin_rows[0])
        wrist = int(skin_rows[-1])
        cuff = int(np.median(contact_rows))
        covers.append((cuff - shoulder) / max(wrist - shoulder, 1))
    return float(np.median(covers)) if covers else 0.3


def _graphic(image: np.ndarray, labels: np.ndarray) -> dict | None:
    upper = labels == UPPER
    if upper.sum() < 200:
        return None
    x0, y0, x1, y1 = _span(upper)
    from scipy import ndimage

    pixels = image.astype(np.float32)
    color = np.median(pixels[upper], axis=0)
    saturation = pixels.max(axis=2) - pixels.min(axis=2)
    chest = np.zeros_like(upper)
    chest[y0 + int((y1 - y0) * 0.18):y0 + int((y1 - y0) * 0.9), x0 + int((x1 - x0) * 0.06):x0 + int((x1 - x0) * 0.82)] = True
    ink = chest & upper & ((saturation > 52) | (pixels.mean(axis=2) < 58))
    labeled, count = ndimage.label(ink)
    kept = np.zeros_like(ink)
    for index in range(1, count + 1):
        component = labeled == index
        if int(component.sum()) < 70:
            continue
        median = np.median(pixels[component], axis=0)
        skin = median[0] > median[2] + 18 and float(median.mean()) > 100
        if skin:
            continue
        kept |= component
    ink = kept
    if ink.sum() < 80:
        print("no graphic")
        return None
    gx0, gy0, gx1, gy1 = _span(ink)
    crop = image[gy0:gy1 + 1, gx0:gx1 + 1].copy()
    keep = ink[gy0:gy1 + 1, gx0:gx1 + 1]
    crop[~keep] = np.array(color, dtype=np.uint8)
    Image.fromarray(crop).save(SAMPLES / "vision-graphic.png")
    box = {
        "x0": (gx0 - x0) / max(x1 - x0, 1),
        "x1": (gx1 - x0) / max(x1 - x0, 1),
        "y0": (gy0 - y0) / max(y1 - y0, 1),
        "y1": (gy1 - y0) / max(y1 - y0, 1),
    }
    print("graphic", {key: round(value, 3) for key, value in box.items()})
    return {"image": Image.fromarray(crop), "box": box, "color": color}


def _apply(edges: dict, graphic: dict | None) -> None:
    import sys

    sys.path.insert(0, str(ROOT / "ai"))
    sys.path.insert(0, str(ROOT / "ai" / "remu"))
    from garment_job import _cut_cloth, _joint_weights
    from skin_garments import body_skin
    from texture_samples import _cotton, _pack

    positions, joints, weights, names, parents, world = body_skin(BODY)
    labels = [str(name or "").lower() for name in names]
    feet_y = float(positions[:, 1].min())
    span = float(positions[:, 1].max()) - feet_y

    def height(name: str) -> float:
        return feet_y + edges[name] * span

    shirt_hem = height("shirt_hem")
    pants_hem = height("pants_hem")
    pants_top = height("pants_top")
    print(
        "avatar hem", round(shirt_hem, 3),
        "pants", round(pants_hem, 3), round(pants_top, 3),
        "sleeve", "long" if edges["long_sleeve"] else "short",
    )

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
    shirt_rgb = [value / 255 for value in edges["shirt_color"]]
    _cut_cloth(BODY, shirt, GARMENTS / "fitted.glb", [*shirt_rgb, 1], 0.014)

    ankle = pants_hem < feet_y + 0.16 * span
    legs = {"left_hip", "right_hip", "left_knee", "right_knee"}
    if ankle:
        legs |= {"left_ankle", "right_ankle"}
    leg_w = _joint_weights(joints, weights, labels, legs)
    foot_w = _joint_weights(joints, weights, labels, {"left_foot", "right_foot"})
    pants = np.flatnonzero(
        (leg_w >= 0.35)
        & (foot_w < 0.25)
        & (positions[:, 1] > pants_hem)
        & (positions[:, 1] < max(shirt_hem, pants_top) + 0.03)
    )
    pants_rgb = [value / 255 for value in edges["pants_color"]]
    _cut_cloth(BODY, pants, GARMENTS / "pants.glb", [*pants_rgb, 1], 0.008, min_faces=40)

    albedo = _cotton(tuple(edges["shirt_color"]), 1024)
    if graphic is not None:
        box = graphic["box"]
        front = Image.fromarray(albedo[:, :512])
        width = max(int((box["x1"] - box["x0"]) * 512), 8)
        height_px = max(int((box["y1"] - box["y0"]) * 1024), 8)
        stamp = graphic["image"].resize((width, height_px), Image.Resampling.LANCZOS)
        stamp_px = np.asarray(stamp).copy()
        background = np.linalg.norm(stamp_px.astype(np.float32) - graphic["color"], axis=2) < 30
        stamp_px[background] = np.array(edges["shirt_color"], dtype=np.uint8)
        front.paste(Image.fromarray(stamp_px), (int(box["x0"] * 512), int(box["y0"] * 1024)))
        albedo[:, :512] = np.asarray(front)
    shirt_albedo = Image.fromarray(albedo)
    shirt_albedo.save(SAMPLES / "vision-shirt.png")
    denim = _cotton(tuple(edges["pants_color"]), 1024)
    _pack(GARMENTS / "fitted.glb", shirt_albedo, 0)
    _pack(GARMENTS / "pants.glb", Image.fromarray(denim), 0)
    print("wore the vision shirt and bottoms")


def main() -> None:
    person_image, person_labels = _segment(PERSON)
    _overlay(person_image, person_labels, "vision-person-mask.png")
    edges = _person(person_image, person_labels)
    print_image, print_labels = _segment(PRINT)
    _overlay(print_image, print_labels, "vision-print-mask.png")
    graphic = _graphic(print_image, print_labels)
    (SAMPLES / "vision-edges.json").write_text(json.dumps(edges, indent=2), encoding="utf-8")
    _apply(edges, graphic)


if __name__ == "__main__":
    main()
