"""Where M2's model files live (ml/models/m02, tracked with DVC; override with M02_ARTIFACTS)."""

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
DIR = Path(os.environ.get("M02_ARTIFACTS", REPO / "ml/models/m02"))
DATASET_IMAGES = Path(os.environ.get("M02_DEMO_IMAGES", REPO / "ml/data/clothing_dataset/images_compressed"))

CP_MODEL = DIR / "outfit_transformer/cp_best.pt"  # pretrained OutfitTransformer, compatibility head
CIR_MODEL = DIR / "outfit_transformer/cir_best.pt"  # pretrained OutfitTransformer, retrieval head
EVAL_METRICS = DIR / "eval_metrics.json"  # our check of the pretrained weights on Polyvore test
PROMPTS = DIR / "prompts.npz"
COMPAT_CALIBRATION = DIR / "compat_calibration.json"  # CP score quantiles per outfit shape
WARDROBE_ITEMS = DIR / "wardrobe_items.json"
WARDROBE_EMB = DIR / "wardrobe_emb.npy"
DEMO_WARDROBES = DIR / "demo_wardrobes.json"
