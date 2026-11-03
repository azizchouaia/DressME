#!/usr/bin/env python3
"""Move the baked garments onto the thin body without dropping their UVs."""

from __future__ import annotations

import os
import shutil
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
BAKED = REPO / "outputs/bmvc/00127/kaggle_refine"
BODY = Path("/mnt/c/Users/NADHIR/Desktop/Dressme/avatar_studio/web/smplx_thin.glb")
OUT = Path("/mnt/c/Users/NADHIR/Desktop/Dressme/avatar_studio/web/garments/textured")
LAYERS = {
    "shirt": "Inner",
    "shorts": "Lower",
    "vest": "Outer",
    "shoes": "Shoes",
}


def parse_obj(path: Path):
    vertices = []
    uvs = []
    faces = []
    for line in path.read_text().splitlines():
        if line.startswith("v "):
            vertices.append([float(part) for part in line.split()[1:4]])
        elif line.startswith("vt "):
            uvs.append([float(part) for part in line.split()[1:3]])
        elif line.startswith("f "):
            corners = []
            for token in line.split()[1:]:
                point, tex, *_ = (token.split("/") + [""])[:2]
                corners.append((int(point) - 1, int(tex) - 1))
            faces.append(corners)
    return (
        np.asarray(vertices, dtype=np.float32),
        np.asarray(uvs, dtype=np.float32),
        faces,
    )


def write_obj(path: Path, vertices, uvs, faces) -> None:
    lines = [f"v {x:.6f} {y:.6f} {z:.6f}" for x, y, z in vertices]
    lines += [f"vt {u:.6f} {v:.6f}" for u, v in uvs]
    for corners in faces:
        bits = [f"{point + 1}/{tex + 1}" for point, tex in corners]
        lines.append("f " + " ".join(bits))
    path.write_text("\n".join(lines) + "\n")


def source_rest(pkl: Path, backend) -> np.ndarray:
    params = _load_params(pkl)
    model = backend._model("male", flat_hand_mean=False, use_pca=True)
    betas = _t(params, "betas", model.shapedirs.device)
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
            "out_dir": str(REG / "_fitbaked"),
        }
    )
    source = source_rest(pkl, backend)
    loved_mesh = trimesh.load(BODY, process=False)
    if isinstance(loved_mesh, trimesh.Scene):
        loved_mesh = trimesh.util.concatenate(tuple(loved_mesh.geometry.values()))
    loved = np.asarray(loved_mesh.vertices, dtype=np.float32)
    scale = float(
        (loved[:, 1].max() - loved[:, 1].min())
        / max(source[:, 1].max() - source[:, 1].min(), 1e-6)
    )
    tree = cKDTree(source)
    print(f"height scale {scale:.4f}")
    chosen = os.environ.get("ONLY", "")
    layers = {name: layer for name, layer in LAYERS.items() if not chosen or name == chosen}
    for name, layer in layers.items():
        src = BAKED / f"00127-{layer}.obj"
        vertices, uvs, faces = parse_obj(src)
        temp = REG / "_fitbaked" / f"{name}_in.obj"
        temp.parent.mkdir(parents=True, exist_ok=True)
        geometry = np.asarray([[corner[0] for corner in face] for face in faces], dtype=np.int64)
        trimesh.Trimesh(vertices, geometry, process=False).export(temp)
        canon = backend.canonicalize(
            CanonicalizeInput(mesh_path=temp, params_path=pkl, gender="male")
        )
        rest = np.asarray(trimesh.load(canon.mesh_path, process=False).vertices, dtype=np.float32)
        if len(rest) != len(vertices):
            raise SystemExit(f"{name}: rest {len(rest)} != baked {len(vertices)}")
        _, nearest = tree.query(rest, k=1)
        placed = loved[nearest] + (rest - source[nearest]) * scale
        write_obj(OUT / f"{name}.obj", placed, uvs, faces)
        shutil.copy2(BAKED / f"00127-{layer}_albedo.png", OUT / f"{name}_albedo.png")
        shutil.copy2(BAKED / f"00127-{layer}_normal.png", OUT / f"{name}_normal.png")
        print(f"{name}: {len(placed)} verts, {len(faces)} faces")


if __name__ == "__main__":
    main()