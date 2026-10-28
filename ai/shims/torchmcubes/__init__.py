"""CPU marching cubes used when the CUDA torchmcubes build is unavailable.

TripoSR calls ``marching_cubes(volume, threshold)`` and expects tensors.
"""

from __future__ import annotations

import torch


def marching_cubes(volume: torch.Tensor, thresh: float) -> tuple[torch.Tensor, torch.Tensor]:
    from skimage.measure import marching_cubes as skimage_marching_cubes

    level = volume.detach().float().cpu().numpy()
    try:
        vertices, faces, _normals, _values = skimage_marching_cubes(level, level=float(thresh))
    except ValueError as exc:
        raise RuntimeError("Marching cubes found no surface in this reconstruction.") from exc
    return (
        torch.from_numpy(vertices.astype("float32")),
        torch.from_numpy(faces.astype("int64")),
    )
