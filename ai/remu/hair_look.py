"""Pick a hairstyle from the person's photos.

CLIP compares the head crop of the front photo with one sentence per style.
The hair mask decides which group is allowed: hair that ends near the ears
is short, hair past the chin in the back photo is long. The pick goes to
labels/look.json; photo_avatar copies it into the avatar profile, and the
viewer chips can override it.

    py -3 ai/remu/hair_look.py DATASET_DIR [--gender male|female]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vision_fit import FACE, HAIR  # noqa: E402

MODEL = "openai/clip-vit-base-patch32"
HAIR_STYLES = {
    "short04": "a photo of a man with a short crop haircut",
    "short02": "a photo of a man with a tall quiff pompadour",
    "short03": "a photo of a person with short hair and a fringe",
    "short01": "a photo of a person with a mohawk",
    "afro01": "a photo of a person with curly afro hair",
    "bob01": "a photo of a woman with a bob haircut",
    "long01": "a photo of a person with long straight hair down",
    "ponytail01": "a photo of a woman with her hair in a ponytail",
    "braid01": "a photo of a woman with a braid",
    "none": "a photo of a bald person",
}
SHORT = {"short04", "short03", "afro01"}
TALL = {"short01", "short02"}
LONG = {"long01", "ponytail01", "braid01", "bob01"}
GENDER_SKIP = {"female": {"short01", "short02", "short04", "none"}, "male": {"ponytail01", "braid01", "bob01", "bob02"}}


def head_crop(image: np.ndarray, labels: np.ndarray) -> Image.Image:
    rows, cols = np.nonzero(np.isin(labels, (FACE, HAIR)))
    if len(rows) < 200:
        raise RuntimeError("The front photo shows too little of the head to pick a hairstyle.")
    top, bottom, left, right = rows.min(), rows.max(), cols.min(), cols.max()
    pad = int(0.35 * max(bottom - top, right - left))
    box = (max(0, left - pad), max(0, top - pad), min(image.shape[1], right + pad), min(image.shape[0], bottom + pad))
    return Image.fromarray(image).crop(box)


def hair_length(front: np.ndarray, back: np.ndarray) -> float:
    """How far the hair reaches below the chin, in face heights."""
    rows = np.nonzero((front == FACE).any(axis=1))[0]
    if not len(rows):
        return 0.0
    chin, height = rows.max(), max(rows.max() - rows.min(), 1)
    lowest = max([np.nonzero((labels == HAIR).sum(axis=1) > 6)[0].max(initial=0) for labels in (front, back)])
    return float((lowest - chin) / height)


def _scores(model, processor, image, prompts: dict) -> dict:
    inputs = processor(text=list(prompts.values()), images=image, return_tensors="pt", padding=True)
    with torch.no_grad():
        probs = model(**inputs).logits_per_image.softmax(dim=1)[0].numpy()
    return dict(zip(prompts, probs.tolist()))


def pick(dataset: Path, gender: str | None = None) -> dict:
    front = np.asarray(Image.open(dataset / "images" / "outfit.png").convert("RGB"))
    front_labels = np.load(dataset / "labels" / "front.npy")
    back_labels = np.load(dataset / "labels" / "back.npy")
    crop = head_crop(front, front_labels)
    model = CLIPModel.from_pretrained(MODEL).eval()
    processor = CLIPProcessor.from_pretrained(MODEL)

    length = hair_length(front_labels, back_labels)
    allowed = SHORT if length < 0.25 else LONG if length > 0.9 else set(HAIR_STYLES) - {"none"}
    if length < 0.25:
        allowed = allowed | TALL
    allowed = (allowed - GENDER_SKIP.get(gender, set())) or allowed
    hair_scores = _scores(model, processor, crop, HAIR_STYLES)
    if length < 0.25:
        for style in TALL:
            hair_scores[style] *= 0.35
    hair = max(allowed, key=hair_scores.get)

    look = {
        "hair": hair,
        "hair_length": round(length, 3),
        "hair_scores": {k: round(v, 3) for k, v in hair_scores.items()},
    }
    (dataset / "labels" / "look.json").write_text(json.dumps(look, indent=2), encoding="utf-8")
    return look


if __name__ == "__main__":
    gender = sys.argv[sys.argv.index("--gender") + 1] if "--gender" in sys.argv else None
    print(json.dumps(pick(Path(sys.argv[1]), gender), indent=2))
