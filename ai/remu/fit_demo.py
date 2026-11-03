#!/usr/bin/env python3
"""Place the demo garments on the loved SMPL-X body.

The registered shells are in the outer-layer pose. Inverse skinning brings
them back to the source rest pose, and each vertex keeps its distance from the
nearest source body vertex when that vertex is moved onto smplx_body.glb.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch
import trimesh
from scipy.spatial import cKDTree
from smplx.lbs import blend_shapes

REPO = Path("/home/nadhir/remu/ReMu")
sys.path.insert(0, str(REPO))

from src.registration.canonicalize import build, CanonicalizeInput  # noqa: E402
from src.registration.canonicalize.knn_lbs import _load_params, _t  # noqa: E402

REG = REPO / "outputs/bmvc/00127/kaggle_reg"
BODY = Path("/mnt/c/Users/NADHIR/Desktop/Dressme/avatar_studio/web/smplx_thin.glb")
OUT = Path("/mnt/c/Users/NADHIR/Desktop/Dressme/avatar_studio/web/garments/fitted")
LAYERS = {
    "shirt": REG / "G_displaced" / "00127-Inner.obj",
    "shorts": REG / "G_displaced" / "00127-Lower.obj",
    "vest": REG / "G_displaced" / "00127-Outer.obj",
}


def source_rest(pkl: Path) -> np.ndarray:
    params = _load_params(pkl)
    model = build(
        {
            "canonicalize": "knn_lbs",
            "body_model_root": str(REPO / "body_models"),
            "device": "cpu",
            "out_dir": str(REG / "_fitrest"),
        }
    )._model("male", flat_hand_mean=False, use_pca=True)
    betas = _t(params, "betas", "cpu")
    if betas.shape[-1] < model.shapedirs.shape[-1]:
        pad = model.shapedirs.shape[-1] - betas.shape[-1]
        betas = torch.nn.functional.pad(betas, (0, pad))
    betas = betas[:, : model.shapedirs.shape[-1]]
    shaped = model.v_template[None] + blend_shapes(betas, model.shapedirs)
    return shaped[0].detach().cpu().numpy().astype(np.float32)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pkl = REG / "smplx" / "00127-Outer.pkl"
    backend = build(
        {
            "canonicalize": "knn_lbs",
            "body_model_root": str(REPO / "body_models"),
            "device": "cuda:0",
            "out_dir": str(REG / "_fitrest"),
        }
    )
    source = source_rest(pkl)
    loved_mesh = trimesh.load(BODY, process=False)
    if isinstance(loved_mesh, trimesh.Scene):
        loved_mesh = trimesh.util.concatenate(tuple(loved_mesh.geometry.values()))
    loved = np.asarray(loved_mesh.vertices, dtype=np.float32)
    if len(loved) != len(source):
        raise SystemExit(f"body vertex count {len(loved)} != source {len(source)}")
    scale = float(
        (loved[:, 1].max() - loved[:, 1].min())
        / max(source[:, 1].max() - source[:, 1].min(), 1e-6)
    )
    tree = cKDTree(source)
    print(f"height scale {scale:.4f}")
    for name, mesh_path in LAYERS.items():
        canon = backend.canonicalize(
            CanonicalizeInput(mesh_path=mesh_path, params_path=pkl, gender="male")
        )
        garment_mesh = trimesh.load(canon.mesh_path, process=False)
        garment = np.asarray(garment_mesh.vertices, dtype=np.float32)
        _, nearest = tree.query(garment, k=1)
        placed = loved[nearest] + (garment - source[nearest]) * scale
        destination = OUT / f"{name}.obj"
        trimesh.Trimesh(placed, np.asarray(garment_mesh.faces), process=False).export(destination)
        offset = np.linalg.norm(garment - source[nearest], axis=1)
        print(f"{name}: {len(placed)} verts, mean offset {offset.mean() * 100:.1f} cm -> {destination}")


if __name__ == "__main__":
    main()
