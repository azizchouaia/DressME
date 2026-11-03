"""Place the TripoSR loafer on both feet and skin it to the body."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai"))

from skin_garments import BODY, body_skin
from smplx_export import pack_glb

SCAN = ROOT / "avatar_studio" / "web" / "garments" / "shoe_scan.glb"
OUT = ROOT / "avatar_studio" / "web" / "garments" / "shoes.glb"


def orient(vertices: np.ndarray, colors: np.ndarray) -> np.ndarray:
    centered = vertices - vertices.mean(axis=0)
    _, _, axes = np.linalg.svd(centered, full_matrices=False)
    aligned = centered @ axes.T
    span = aligned.max(axis=0) - aligned.min(axis=0)
    order = np.argsort(span)  # smallest, middle, largest
    # A loafer is long, then tall, then thin.
    width, height, length = (aligned[:, order[0]], aligned[:, order[1]], aligned[:, order[2]])
    standing = np.stack([width, height, length], axis=1)
    standing[:, 1] -= standing[:, 1].min()
    # The toe is the narrower end.
    midpoint = standing[:, 2].mean()
    toe = standing[standing[:, 2] > midpoint]
    heel = standing[standing[:, 2] <= midpoint]
    toe_width = toe[:, 0].max() - toe[:, 0].min() if len(toe) else 1
    heel_width = heel[:, 0].max() - heel[:, 0].min() if len(heel) else 0
    if toe_width > heel_width:
        standing[:, 2] *= -1
        standing[:, 2] -= standing[:, 2].min()
    else:
        standing[:, 2] -= standing[:, 2].min()
    standing[:, 0] -= (standing[:, 0].min() + standing[:, 0].max()) / 2
    dark = colors.mean(axis=1) < 0.25
    if dark.any() and float(standing[dark, 1].mean()) > float(standing[:, 1].mean()):
        standing[:, 1] = standing[:, 1].max() - standing[:, 1]
    return standing.astype(np.float32)


def foot_cloud(positions, world, names, side: str) -> np.ndarray:
    foot = world[names.index(f"{side}_foot")]
    ankle = world[names.index(f"{side}_ankle")]
    other = world[names.index("right_foot" if side == "left" else "left_foot")]
    distance = np.linalg.norm(positions - foot, axis=1)
    other_distance = np.linalg.norm(positions - other, axis=1)
    return positions[(distance < other_distance) & (positions[:, 1] <= ankle[1] + 0.02) & (distance < 0.16)]


def place(shoe: np.ndarray, foot: np.ndarray) -> np.ndarray:
    low = foot.min(axis=0)
    high = foot.max(axis=0)
    target = high - low
    current = shoe.max(axis=0) - shoe.min(axis=0)
    current = np.maximum(current, 1e-4)
    scale = np.array(
        [
            target[0] / current[0] * 1.45,
            max(target[1], 0.06) / current[1] * 1.7,
            target[2] / current[2] * 1.45,
        ],
        np.float32,
    )
    fitted = shoe * scale
    fitted[:, 0] += (low[0] + high[0]) / 2 - (fitted[:, 0].min() + fitted[:, 0].max()) / 2
    fitted[:, 2] += (low[2] + high[2]) / 2 - (fitted[:, 2].min() + fitted[:, 2].max()) / 2
    fitted[:, 1] += low[1] - fitted[:, 1].min() - 0.006
    return fitted.astype(np.float32)


def main() -> None:
    loaded = trimesh.load(SCAN, force="mesh")
    raw = np.asarray(loaded.vertices, np.float32)
    colors = np.asarray(loaded.visual.vertex_colors)[:, :3].astype(np.float32) / 255
    faces = np.asarray(loaded.faces, np.int64)
    navy = (colors[:, 2] > colors[:, 0] + 0.04) & (colors[:, 2] > 0.12) & (colors[:, 0] < 0.45)
    brown = (colors[:, 0] > colors[:, 2] + 0.06) & (colors[:, 0] > 0.18) & (colors[:, 0] < 0.75)
    dark = colors.mean(axis=1) < 0.22
    keep_vertex = navy | brown | dark
    keep = keep_vertex[faces].all(axis=1)
    faces = faces[keep]
    used = np.unique(faces)
    remap = np.full(len(raw), -1, np.int64)
    remap[used] = np.arange(len(used))
    faces = remap[faces]
    shoe = orient(raw[used], colors[used])
    colors = colors[used]
    positions, joints, weights, names, parents, world = body_skin(BODY)
    tree = cKDTree(positions)

    parts = []
    for side, mirror in (("left", False), ("right", True)):
        local = shoe.copy()
        part_faces = faces
        if mirror:
            local[:, 0] *= -1
            part_faces = faces[:, ::-1]
        fitted = place(local, foot_cloud(positions, world, names, side))
        parts.append((fitted, part_faces, colors))

    vertices = []
    all_faces = []
    all_colors = []
    offset = 0
    for fitted, part_faces, part_colors in parts:
        vertices.append(fitted)
        all_faces.append(part_faces + offset)
        all_colors.append(part_colors)
        offset += len(fitted)
    vertices = np.vstack(vertices)
    all_faces = np.vstack(all_faces)
    all_colors = np.vstack(all_colors)
    _, nearest = tree.query(vertices, k=1)
    packed_joints = joints[nearest]
    packed_weights = weights[nearest].astype(np.float32)
    packed_weights /= np.maximum(packed_weights.sum(axis=1, keepdims=True), 1e-8)
    from smplx_export import vertex_normals

    pack_glb(
        vertices,
        vertex_normals(vertices, all_faces),
        packed_joints,
        packed_weights,
        all_faces,
        names,
        parents,
        world,
        OUT,
        colors=all_colors,
    )
    print(f"shoes {len(vertices)} vertices -> {OUT.name}")


if __name__ == "__main__":
    main()
