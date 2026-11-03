"""Build the shirt layer and the pants layer the way the working run was fed.

The shirt layer keeps the person in the yellow shirt.
The pants layer matches the working lower prompt: bare chest, pants still on.
Both sit on a plain background, front and back.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from vision_fit import FACE, LEFT_ARM, RIGHT_ARM, UPPER, _segment

ROOT = Path(__file__).resolve().parents[2]
FRONT = Path(r"C:\Users\NADHIR\.cursor\projects\c-Users-NADHIR-Desktop-Dressme\assets\9efd5fd7-94d3-4e7e-b965-e20ff06f445f-6aa4ff4e-b7d1-4c95-b42a-a54a5ad48ee1.jpg")
BACK = Path(r"C:\Users\NADHIR\.cursor\projects\c-Users-NADHIR-Desktop-Dressme\assets\b1f3f5c7-a16f-4497-a68d-2dc2be05ba12-71ec2460-e9fc-49b1-b841-a49181b85942.jpg")
OUT = ROOT / "avatar_studio" / "web" / "garments" / "saved" / "auto_test" / "layers"
DATASET = ROOT / "avatar_studio" / "web" / "garments" / "saved" / "garment_job" / "dataset"
TEMPLATES = ROOT / "ai" / "remu" / "shirt_input" / "templates"
def _person(labels: np.ndarray) -> np.ndarray:
    mask = labels != 0
    mask = ndimage.binary_closing(mask, iterations=2)
    return ndimage.binary_fill_holes(mask)


def _frame(image: np.ndarray, mask: np.ndarray) -> Image.Image:
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = int(ys.min()), int(ys.max()), int(xs.min()), int(xs.max())
    crop = image[y0:y1 + 1, x0:x1 + 1].copy()
    keep = mask[y0:y1 + 1, x0:x1 + 1]
    rgba = np.zeros((crop.shape[0], crop.shape[1], 4), dtype=np.uint8)
    rgba[..., :3] = crop
    rgba[..., 3] = keep.astype(np.uint8) * 255
    side = 1024
    scale = min((side * 0.88) / crop.shape[0], (side * 0.78) / crop.shape[1])
    resized = Image.fromarray(rgba).resize(
        (max(1, int(crop.shape[1] * scale)), max(1, int(crop.shape[0] * scale))),
        Image.Resampling.LANCZOS,
    )
    framed = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    x = (side - resized.width) // 2
    y = side - 12 - resized.height
    framed.paste(resized, (x, max(0, y)))
    return framed


def _skin(image: np.ndarray, labels: np.ndarray) -> np.ndarray:
    arm = image[np.isin(labels, (LEFT_ARM, RIGHT_ARM))]
    if len(arm) < 20:
        return np.array([196, 154, 124], dtype=np.uint8)
    bright = arm[arm.mean(axis=1) >= np.percentile(arm.mean(axis=1), 55)]
    return np.median(bright, axis=0).astype(np.uint8)


def _layer(path: Path, bare: bool) -> Image.Image:
    image, labels = _segment(path)
    if bare:
        image = image.copy()
        image[labels == UPPER] = _skin(image, labels)
    return _frame(image, _person(labels))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    layers = {
        "front-inner": _layer(FRONT, False),
        "front-lower": _layer(FRONT, True),
        "back-inner": _layer(BACK, False),
        "back-lower": _layer(BACK, True),
    }
    for name, image in layers.items():
        image.save(OUT / f"{name}.png")
        print(name, image.mode, image.getextrema()[3])
        print("saved", name)

    if DATASET.exists():
        shutil.rmtree(DATASET)
    for name in ("images", "back_images", "smplx", "templates"):
        (DATASET / name).mkdir(parents=True)
    layers["front-inner"].save(DATASET / "images" / "garment.png")
    layers["front-lower"].save(DATASET / "images" / "autotest_Lower.png")
    layers["back-inner"].save(DATASET / "back_images" / "garment.png")
    layers["back-lower"].save(DATASET / "back_images" / "autotest_Lower.png")
    canon = TEMPLATES / "smplx_canonical.obj"
    for stem in ("garment", "autotest_Lower"):
        shutil.copy(canon, DATASET / "smplx" / f"{stem}_smplx.obj")
    for name in ("smplx_canonical.obj", "smplx_watertight.pkl"):
        shutil.copy(TEMPLATES / name, DATASET / "templates" / name)
    (DATASET / "dataset-metadata.json").write_text(
        '{"title": "DressMe garment try", "id": "nadhirmaamar/dressme-garment-try", "licenses": [{"name": "other"}]}',
        encoding="utf-8",
    )
    print("dataset ready")


if __name__ == "__main__":
    main()
