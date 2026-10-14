"""Pretrained OutfitTransformer (Sarkar et al., CVPRW 2022), used as-is, no training here.

Weights: huggingface.co/FlorindoDev/OutfitTransformer-weights (Polyvore Outfits, nondisjoint),
code: github.com/FlorindoDev/OutfitTransformer. The modules below rebuild that architecture so the published
state_dicts load with strict=True.

Input of both models: item vectors of 1024 floats = [FashionCLIP image (512) | FashionCLIP text (512)].

* CP  (compatibility prediction): learned [CP] token + the items -> 6-layer transformer -> P(outfit is good).
  Published validation AUC 0.952.
* CIR (complementary item retrieval): a learned [CIR] token + a partial outfit -> 128-d "ideal missing piece"
  embedding; every candidate item is embedded alone into the same space; nearest = best fit.
  Published validation FITB accuracy 68.3 % (4 choices), recall@2 87.9 %.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from . import artifacts

D_MOD, D = 512, 1024


def _encoder(cfg: dict) -> nn.TransformerEncoder:
    layer = nn.TransformerEncoderLayer(
        d_model=2 * cfg["modality_embedding_dim"],
        nhead=cfg["attention_heads"],
        dim_feedforward=cfg["feedforward_dim"],
        dropout=cfg["dropout"],
        activation=nn.Mish(),
        layer_norm_eps=cfg["layer_norm_epsilon"],
        batch_first=True,
        norm_first=cfg["norm_first"],
    )
    return nn.TransformerEncoder(layer, cfg["layers"], enable_nested_tensor=False)


class _TaskEmbedding(nn.Module):
    def __init__(self):
        super().__init__()
        self.embedding = nn.Parameter(torch.zeros(D_MOD))


class _CP(nn.Module):
    def __init__(self, cfg: dict):
        super().__init__()
        self.task_embedding = _TaskEmbedding()
        self.predict_emb = nn.Parameter(torch.zeros(D_MOD))
        self.encoder = _encoder(cfg)
        self.head = nn.Module()
        self.head.classifier = nn.Sequential(nn.Dropout(cfg["dropout"]), nn.Linear(D, 1), nn.Sigmoid())

    def forward(self, x: torch.Tensor, pad: torch.Tensor) -> torch.Tensor:
        tok = F.normalize(torch.cat([self.task_embedding.embedding, self.predict_emb]), dim=-1, eps=1e-12)
        h = torch.cat([tok.view(1, 1, -1).expand(len(x), -1, -1), x], 1)
        m = torch.cat([torch.zeros_like(pad[:, :1]), pad], 1)
        return self.head.classifier(self.encoder(h, src_key_padding_mask=m)[:, 0]).squeeze(-1)


class _CIR(nn.Module):
    def __init__(self, cfg: dict):
        super().__init__()
        self.task_embedding = _TaskEmbedding()
        self.embed_emb = nn.Parameter(torch.zeros(D_MOD))
        self.encoder = _encoder(cfg)
        self.head = nn.Module()
        self.head.projection = nn.Linear(D, 128, bias=False)

    def query(self, x: torch.Tensor, pad: torch.Tensor) -> torch.Tensor:
        tok = F.normalize(torch.cat([self.task_embedding.embedding, self.embed_emb]), dim=-1, eps=1e-12)
        h = torch.cat([tok.view(1, 1, -1).expand(len(x), -1, -1), x], 1)
        m = torch.cat([torch.zeros_like(pad[:, :1]), pad], 1)
        return self.head.projection(self.encoder(h, src_key_padding_mask=m)[:, 0])

    def items(self, x: torch.Tensor) -> torch.Tensor:
        """x (N, 1024): each item encoded alone."""
        return self.head.projection(self.encoder(x[:, None, :])[:, 0])


class _Wrapper(nn.Module):
    """Mirrors the checkpoint's top-level layout: common.padding_embedding + cp.* or cir.*."""

    def __init__(self, kind: str, cfg: dict):
        super().__init__()
        self.common = nn.Module()
        self.common.padding_embedding = nn.Parameter(torch.zeros(D))
        setattr(self, kind, _CP(cfg) if kind == "cp" else _CIR(cfg))


def _load(kind: str, path: Path) -> _Wrapper:
    ckpt = torch.load(path, map_location="cpu", weights_only=False)
    cfg = ckpt["run_config"]["model"]
    cfg = cfg.get("transformer", cfg)  # CP stores the transformer config flat, CIR nests it
    model = _Wrapper(kind, cfg)
    model.load_state_dict(ckpt["model_state_dict"], strict=True)
    return model.eval()


def _pad(outfits: list[np.ndarray], padding: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    n = max(len(o) for o in outfits)
    x = padding.view(1, 1, -1).repeat(len(outfits), n, 1)
    pad = torch.ones(len(outfits), n, dtype=torch.bool)
    for i, o in enumerate(outfits):
        x[i, : len(o)] = torch.from_numpy(np.asarray(o, np.float32))
        pad[i, : len(o)] = False
    return x, pad


class OutfitTransformer:
    """Loads both pretrained heads once; all methods take item vectors (numpy, 1024-d)."""

    def __init__(self, cp_path: Path = artifacts.CP_MODEL, cir_path: Path = artifacts.CIR_MODEL):
        torch.set_num_threads(min(8, torch.get_num_threads()))
        self.cp = _load("cp", cp_path)
        self.cir = _load("cir", cir_path)

    @torch.no_grad()
    def compatibility(self, outfits: list[np.ndarray], batch: int = 256) -> np.ndarray:
        """outfits: list of (n_items, 1024) arrays -> P(compatible) for each."""
        out = []
        for i in range(0, len(outfits), batch):
            x, pad = _pad(outfits[i : i + batch], self.cp.common.padding_embedding)
            out.append(self.cp.cp(x, pad).numpy())
        return np.concatenate(out) if out else np.zeros(0, np.float32)

    @torch.no_grad()
    def query(self, partial_outfits: list[np.ndarray]) -> np.ndarray:
        """Partial outfits -> (B, 128) embedding of the ideal missing piece."""
        x, pad = _pad(partial_outfits, self.cir.common.padding_embedding)
        return self.cir.cir.query(x, pad).numpy()

    @torch.no_grad()
    def item_space(self, vectors: np.ndarray) -> np.ndarray:
        """Items -> (N, 128) retrieval embeddings (cache them: they do not depend on the outfit)."""
        return self.cir.cir.items(torch.from_numpy(np.asarray(vectors, np.float32))).numpy()
