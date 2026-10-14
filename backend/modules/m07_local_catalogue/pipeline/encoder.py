"""FashionCLIP (patrickjohncyh/fashion-clip) run locally: photos and text in the same 512-d space.

torch / transformers are imported lazily so the rest of the agent (and CI) works without them.
The first load downloads ~600 MB into the Hugging Face cache; later loads are local.
"""

from collections.abc import Sequence
from pathlib import Path

import numpy as np

DEFAULT_MODEL = "patrickjohncyh/fashion-clip"


def _l2(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=-1, keepdims=True)
    return (x / np.clip(norms, 1e-12, None)).astype(np.float32)


class FashionCLIP:
    dim = 512

    def __init__(self, model_name: str = DEFAULT_MODEL, device: str | None = None):
        import torch
        from transformers import CLIPModel, CLIPProcessor

        self._torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = CLIPModel.from_pretrained(model_name).to(self.device).eval()
        self.processor = CLIPProcessor.from_pretrained(model_name)
        self.model_name = model_name

    @staticmethod
    def _features(out) -> "object":
        # transformers < 5 returns the projected tensor, >= 5 a ModelOutput whose pooler_output is it.
        return getattr(out, "pooler_output", out)

    def encode_texts(self, texts: Sequence[str]) -> np.ndarray:
        with self._torch.no_grad():
            inputs = self.processor(text=list(texts), return_tensors="pt", padding=True, truncation=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            feats = self._features(self.model.get_text_features(**inputs))
        return _l2(feats.cpu().numpy())

    def encode_images(self, paths: Sequence[str | Path], batch_size: int = 32) -> np.ndarray:
        from PIL import Image

        chunks = []
        for start in range(0, len(paths), batch_size):
            images = [Image.open(p).convert("RGB") for p in paths[start : start + batch_size]]
            with self._torch.no_grad():
                inputs = self.processor(images=images, return_tensors="pt")
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                chunks.append(self._features(self.model.get_image_features(**inputs)).cpu().numpy())
        return _l2(np.concatenate(chunks)) if chunks else np.zeros((0, self.dim), np.float32)
