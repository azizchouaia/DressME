"""FashionCLIP (patrickjohncyh/fashion-clip): image embeddings + zero-shot. Loaded once, lazily, CPU ok."""

import threading

import numpy as np

from ..config import get_config
from .classifier import softmax

_model = None
_lock = threading.Lock()


def _l2(x: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.clip(norm, 1e-12, None)


def _features(out):
    """transformers 4.x returns a tensor, 5.x may return a model output: accept both."""
    if hasattr(out, "detach"):
        return out
    for name in ("image_embeds", "text_embeds", "pooler_output"):
        value = getattr(out, name, None)
        if value is not None:
            return value
    return out[0]


class FashionClip:
    def __init__(self, model_name: str, device: str = "cpu"):
        import torch
        from transformers import CLIPModel, CLIPProcessor

        self._torch = torch
        self.device = device
        self.model = CLIPModel.from_pretrained(model_name).to(device).eval()
        self.processor = CLIPProcessor.from_pretrained(model_name)
        self.logit_scale = float(self.model.logit_scale.exp())
        self._text_cache: dict[tuple[str, ...], np.ndarray] = {}

    def embed_image(self, image) -> np.ndarray:
        """PIL image -> (512,) float32, L2-normalised."""
        inputs = self.processor(images=image.convert("RGB"), return_tensors="pt").to(self.device)
        with self._torch.inference_mode():
            feats = _features(self.model.get_image_features(**inputs))
        return _l2(feats[0].float().cpu().numpy())

    def embed_texts(self, prompts: tuple[str, ...]) -> np.ndarray:
        if prompts not in self._text_cache:
            inputs = self.processor(text=list(prompts), return_tensors="pt", padding=True, truncation=True)
            inputs = inputs.to(self.device)
            with self._torch.inference_mode():
                feats = _features(self.model.get_text_features(**inputs))
            self._text_cache[prompts] = _l2(feats.float().cpu().numpy())
        return self._text_cache[prompts]

    def zero_shot(
        self, image_emb: np.ndarray, prompts: tuple[str, ...], scale: float | None = None
    ) -> np.ndarray:
        """Softmax over the scaled cosine similarities image <-> each prompt (default: the model's scale)."""
        return softmax((scale or self.logit_scale) * (self.embed_texts(prompts) @ image_emb))


def get_clip() -> FashionClip:
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                models = get_config().models
                _model = FashionClip(models.clip, models.device)
    return _model
