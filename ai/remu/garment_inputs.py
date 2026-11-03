"""Prepare a front and a back photo for SiTH body fitting and reconstruction.

Each photo is checked, cut out, and framed on a 1024 square. The back photo is
scaled and moved so that, mirrored, its outline sits on the front outline:
SiTH mirrors the back image and reuses the front mask for it. Body keypoints
are written as OpenPose COCO-25 JSON, which SiTH's fit.py reads.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai" / "remu"))

from vision_fit import FACE, HAIR, HAT, LEFT_LEG, LEFT_SHOE, PANTS, RIGHT_LEG, RIGHT_SHOE, SKIRT, UPPER, _segment  # noqa: E402

SIDE = 1024
TEMPLATES = ROOT / "ai" / "remu" / "shirt_input" / "templates"
STEM = "outfit"
FEET = (LEFT_SHOE, RIGHT_SHOE, LEFT_LEG, RIGHT_LEG)
COCO_TO_BODY25 = {0: 0, 6: 2, 8: 3, 10: 4, 5: 5, 7: 6, 9: 7, 12: 9, 14: 10, 16: 11, 11: 12, 13: 13, 15: 14, 2: 15, 1: 16, 4: 17, 3: 18}


class PhotoProblem(RuntimeError):
    pass


def _trim_floor(labels: np.ndarray) -> np.ndarray:
    """Drop shoe pixels outside the leg columns; floor mats get labelled as shoes."""
    labels = labels.copy()
    shoes = np.isin(labels, (LEFT_SHOE, RIGHT_SHOE))
    legs = np.isin(labels, (PANTS, SKIRT, LEFT_LEG, RIGHT_LEG))
    if not shoes.any() or not legs.any():
        return labels
    margin = max(4, int(0.02 * labels.shape[1]))
    reach = max(8, int(0.06 * labels.shape[0]))
    for y in np.nonzero(shoes.any(axis=1))[0]:
        above = legs[max(0, y - reach):y + 1].any(axis=0)
        allowed = ndimage.binary_dilation(above, iterations=margin)
        labels[y, shoes[y] & ~allowed] = 0
    return labels


def white_balance(image: np.ndarray, labels: np.ndarray, target: float = 245.0) -> tuple[np.ndarray, list[float]]:
    """Scale each channel so the brightest neutral background (a wall, a door frame) reads white."""
    background = image[labels == 0].astype(np.float32)
    if len(background) < 1000:
        return image, [1.0, 1.0, 1.0]
    light = background @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    spread = background.max(axis=1) - background.min(axis=1)
    picked = background[(light >= np.percentile(light, 90)) & (spread < 40)]
    if len(picked) < 200:
        return image, [1.0, 1.0, 1.0]
    gains = np.clip(target / np.maximum(picked.mean(axis=0), 1.0), 0.8, 1.5)
    balanced = np.clip(image.astype(np.float32) * gains, 0, 255).astype(np.uint8)
    return balanced, [round(float(g), 3) for g in gains]


def _person_mask(labels: np.ndarray) -> np.ndarray:
    mask = ndimage.binary_closing(labels != 0, iterations=2)
    mask = ndimage.binary_fill_holes(mask)
    labeled, count = ndimage.label(mask)
    if count == 0:
        raise PhotoProblem("No person was found in the photo.")
    sizes = ndimage.sum(mask, labeled, range(1, count + 1))
    return labeled == int(np.argmax(sizes)) + 1


def check(labels: np.ndarray, view: str) -> None:
    person = _person_mask(labels)
    height, width = labels.shape
    ys, xs = np.nonzero(person)
    if person.mean() < 0.04:
        raise PhotoProblem(f"The {view} photo: the person is too small. Stand closer.")
    if ys.min() <= 2 or xs.min() <= 2 or xs.max() >= width - 3:
        raise PhotoProblem(f"The {view} photo: the body touches the edge. Keep the whole body in frame.")
    if ys.max() >= height - 2 and not np.isin(labels[-3:], FEET).any():
        raise PhotoProblem(f"The {view} photo: the feet are cut off.")
    if not np.isin(labels, FEET).any():
        raise PhotoProblem(f"The {view} photo: the feet are not visible.")
    if view == "front" and not np.isin(labels, (HAT, HAIR, FACE)).any():
        raise PhotoProblem("The front photo: the head is not visible.")
    if (labels == UPPER).sum() < 0.01 * person.sum():
        raise PhotoProblem(f"The {view} photo: no top was found.")
    if np.isin(labels, (PANTS, SKIRT)).sum() < 0.01 * person.sum():
        raise PhotoProblem(f"The {view} photo: no pants, shorts, or skirt were found.")


def _garment_box(labels: np.ndarray) -> tuple[float, float, float]:
    """(top y, bottom y, center x) of the top and bottom garments together."""
    ys, xs = np.nonzero(np.isin(labels, (UPPER, PANTS, SKIRT)))
    return float(ys.min()), float(ys.max() + 1), float(xs.mean())


def _frame(image: np.ndarray, labels: np.ndarray, mask: np.ndarray, place: tuple[float, tuple, tuple] | None = None):
    """Crop to the mask, scale, and place it on the square.

    place is (scale, source point, target point): the source point in the photo
    lands on the target point. Without it the person fills 88% of the height,
    centered, with the feet 12 px above the bottom.
    """
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    crop_h, crop_w = y1 - y0 + 1, x1 - x0 + 1
    if place is None:
        place = (SIDE * 0.88 / crop_h, ((x0 + x1 + 1) / 2, y1 + 1), (SIDE / 2, SIDE - 12))
    scale, (source_x, source_y), (target_x, target_y) = place
    new_w, new_h = max(1, round(crop_w * scale)), max(1, round(crop_h * scale))
    rgba = np.zeros((crop_h, crop_w, 4), dtype=np.uint8)
    rgba[..., :3] = image[y0:y1 + 1, x0:x1 + 1]
    rgba[..., 3] = mask[y0:y1 + 1, x0:x1 + 1].astype(np.uint8) * 255
    resized = Image.fromarray(rgba).resize((new_w, new_h), Image.Resampling.LANCZOS)
    parsed = Image.fromarray(labels[y0:y1 + 1, x0:x1 + 1]).resize((new_w, new_h), Image.Resampling.NEAREST)
    left = round(target_x - (source_x - x0) * scale)
    top = round(target_y - (source_y - y0) * scale)
    canvas = Image.new("RGBA", (SIDE, SIDE), (0, 0, 0, 0))
    canvas.paste(resized, (left, top))
    label_canvas = Image.new("L", (SIDE, SIDE), 0)
    label_canvas.paste(parsed, (left, top))
    framed = np.asarray(canvas).copy()
    framed[..., 3] = np.where(framed[..., 3] > 127, 255, 0)
    framed[framed[..., 3] == 0, :3] = 0
    out_labels = np.asarray(label_canvas).copy()
    out_labels[framed[..., 3] == 0] = 0
    return framed, out_labels


def keypoints(rgba: np.ndarray) -> dict:
    import torch
    from transformers import AutoProcessor, VitPoseForPoseEstimation

    processor = AutoProcessor.from_pretrained("usyd-community/vitpose-base-simple")
    model = VitPoseForPoseEstimation.from_pretrained("usyd-community/vitpose-base-simple")
    model.eval()
    rgb = rgba[..., :3].copy()
    rgb[rgba[..., 3] == 0] = 255
    ys, xs = np.nonzero(rgba[..., 3])
    pad = 16
    x0, y0 = max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad)
    x1, y1 = min(SIDE - 1, int(xs.max()) + pad), min(SIDE - 1, int(ys.max()) + pad)
    boxes = [[[x0, y0, x1 - x0, y1 - y0]]]
    inputs = processor(Image.fromarray(rgb), boxes=boxes, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    result = processor.post_process_pose_estimation(outputs, boxes=boxes)[0][0]
    coco = result["keypoints"].numpy()
    scores = result["scores"].numpy()
    body = np.zeros((25, 3), dtype=np.float32)
    for source, target in COCO_TO_BODY25.items():
        body[target] = (coco[source][0], coco[source][1], scores[source])
    for target, (a, b) in {1: (5, 6), 8: (11, 12)}.items():
        if min(scores[a], scores[b]) > 0.05:
            body[target] = (*((coco[a] + coco[b]) / 2), min(scores[a], scores[b]))
    return {
        "version": 1.3,
        "people": [{
            "pose_keypoints_2d": body.reshape(-1).round(3).tolist(),
            "hand_left_keypoints_2d": [0.0] * 63,
            "hand_right_keypoints_2d": [0.0] * 63,
            "face_keypoints_2d": [0.0] * 210,
        }],
    }


def prepare(front: Path, back: Path, dataset: Path, dataset_id: str, mirror_front: bool = False) -> dict:
    """mirror_front undoes a selfie camera that saved the front photo mirrored."""
    front_image, front_labels = _segment(front)
    back_image, back_labels = _segment(back)
    front_image, front_gains = white_balance(front_image, front_labels)
    back_image, back_gains = white_balance(back_image, back_labels)
    if mirror_front:
        front_image, front_labels = front_image[:, ::-1].copy(), front_labels[:, ::-1].copy()
    front_labels, back_labels = _trim_floor(front_labels), _trim_floor(back_labels)
    check(front_labels, "front")
    check(back_labels, "back")
    front_rgba, front_framed_labels = _frame(front_image, front_labels, _person_mask(front_labels))
    front_top, front_bottom, front_x = _garment_box(front_framed_labels)
    back_top, back_bottom, back_x = _garment_box(back_labels)
    scale = (front_bottom - front_top) / (back_bottom - back_top)
    place = (scale, (back_x, back_bottom), (SIDE - front_x, front_bottom))
    back_rgba, back_framed_labels = _frame(back_image, back_labels, _person_mask(back_labels), place)
    flipped = back_rgba[:, ::-1, 3] > 0
    front_mask = front_rgba[..., 3] > 0
    overlap = float((flipped & front_mask).sum() / max((flipped | front_mask).sum(), 1))
    if overlap < 0.55:
        raise PhotoProblem("The front and back photos are in different poses. Take both with the same stance.")

    if dataset.exists():
        shutil.rmtree(dataset)
    for name in ("images", "back_images", "templates", "labels"):
        (dataset / name).mkdir(parents=True)
    Image.fromarray(front_rgba).save(dataset / "images" / f"{STEM}.png")
    Image.fromarray(back_rgba).save(dataset / "back_images" / f"{STEM}.png")
    np.save(dataset / "labels" / "front.npy", front_framed_labels)
    np.save(dataset / "labels" / "back.npy", back_framed_labels)
    record = keypoints(front_rgba)
    (dataset / "images" / f"{STEM}_keypoints.json").write_text(json.dumps(record), encoding="utf-8")
    for name in ("smplx_canonical.obj", "smplx_watertight.pkl"):
        shutil.copy(TEMPLATES / name, dataset / "templates" / name)
    (dataset / "dataset-metadata.json").write_text(
        json.dumps({"title": "DressMe garment photos", "id": dataset_id, "licenses": [{"name": "other"}]}),
        encoding="utf-8",
    )
    summary = {"overlap": round(overlap, 3), "white_balance": {"front": front_gains, "back": back_gains}, "keypoints": int(sum(1 for i in range(25) if record["people"][0]["pose_keypoints_2d"][i * 3 + 2] > 0.3))}
    (dataset / "labels" / "inputs.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--mirror-front"]
    print(json.dumps(prepare(Path(args[0]), Path(args[1]), Path(args[2]), args[3], "--mirror-front" in sys.argv), indent=2))
