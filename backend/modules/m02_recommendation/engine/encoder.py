"""FashionCLIP (patrickjohncyh/fashion-clip, pretrained, not fine-tuned) image + text encoder.

An item vector is what the pretrained OutfitTransformer expects (1024 floats):
    concat( L2(image embedding 512), L2(text embedding 512) )
where the text is a short description of the piece, e.g. "black striped t-shirt".
In production M1 computes these vectors; M2 only needs the encoder for text prompts and the demo wardrobe.
"""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np
import torch

MODEL_ID = "patrickjohncyh/fashion-clip"


@lru_cache(maxsize=1)
def _load():
    from transformers import CLIPModel, CLIPProcessor

    torch.set_num_threads(min(16, os.cpu_count() or 4))
    model = CLIPModel.from_pretrained(MODEL_ID).eval()
    return model, CLIPProcessor.from_pretrained(MODEL_ID)


def _l2(x: torch.Tensor) -> np.ndarray:
    return torch.nn.functional.normalize(x, dim=-1).float().cpu().numpy()


@torch.no_grad()
def embed_images(images) -> np.ndarray:
    """PIL images -> (N, 512) L2-normalised image embeddings."""
    model, proc = _load()
    px = proc(images=[im.convert("RGB") for im in images], return_tensors="pt")["pixel_values"]
    return _l2(model.visual_projection(model.vision_model(pixel_values=px).pooler_output))


@torch.no_grad()
def embed_texts(texts: list[str]) -> np.ndarray:
    """Strings -> (N, 512) L2-normalised text embeddings."""
    model, proc = _load()
    tok = proc(text=list(texts), return_tensors="pt", padding=True, truncation=True, max_length=77)
    return _l2(model.text_projection(model.text_model(input_ids=tok["input_ids"], attention_mask=tok.get("attention_mask")).pooler_output))


def item_vectors(image_emb: np.ndarray, descriptions: list[str]) -> np.ndarray:
    """(N, 512) image embeddings + descriptions -> (N, 1024) OutfitTransformer item vectors."""
    return np.concatenate([image_emb, embed_texts(descriptions)], 1).astype(np.float32)
