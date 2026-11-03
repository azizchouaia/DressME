"""FashionCLIP image and text embeddings.

This is patrickjohncyh/fashion-clip, the pretrained model already used by
recommender/embed_images.py. The first call downloads the weights.
"""

from __future__ import annotations

import numpy as np

from recommender.engine import average_vectors, unit

MODEL_ID = "patrickjohncyh/fashion-clip"


class FashionCLIP:
    dim = 512

    def __init__(self) -> None:
        self._model = None
        self._processor = None
        self._device = "cpu"

    def _load(self):
        if self._model is not None:
            return
        import torch
        from transformers import CLIPModel, CLIPProcessor

        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._processor = CLIPProcessor.from_pretrained(MODEL_ID)
        self._model = CLIPModel.from_pretrained(MODEL_ID).to(self._device)
        self._model.eval()

    def _features(self, inputs: dict) -> np.ndarray:
        import torch

        self._load()
        moved = {name: value.to(self._device) for name, value in inputs.items()}
        with torch.no_grad():
            if "pixel_values" in moved and "input_ids" not in moved:
                features = self._model.get_image_features(**moved)
            else:
                features = self._model.get_text_features(**moved)
        if hasattr(features, "pooler_output"):
            features = features.pooler_output
        return unit(features.detach().cpu().numpy().astype(np.float32)[0])

    def embed_text(self, text: str) -> np.ndarray:
        self._load()
        inputs = self._processor(text=[text], return_tensors="pt", padding=True, truncation=True)
        return self._features(inputs)

    def embed_image(self, data: bytes) -> np.ndarray:
        from io import BytesIO

        from PIL import Image

        self._load()
        image = Image.open(BytesIO(data)).convert("RGB")
        inputs = self._processor(images=[image], return_tensors="pt")
        return self._features(inputs)

    def embed_frames(self, frames: list[bytes]) -> np.ndarray:
        return average_vectors([self.embed_image(frame) for frame in frames])


PROTOTYPE_TEXT = {
    "top": "a photo of a shirt or t-shirt",
    "bottom": "a photo of pants jeans or shorts",
    "outer": "a photo of a jacket or coat",
    "shoes": "a photo of shoes",
}
