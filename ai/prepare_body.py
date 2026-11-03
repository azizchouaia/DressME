"""Turn a photo reconstruction into a standing body mesh.

The result is smoothed enough to use later as a skeleton base: one subdivision,
then Taubin smoothing so the marching-cubes steps fade without melting the
limbs. The body is scaled to 1.75 m, centered on X and Z, with the feet on
y = 0 and the head toward +Y.
"""

from __future__ import annotations

import numpy as np
import trimesh
from scipy.spatial import cKDTree
from trimesh.smoothing import filter_taubin

BODY_HEIGHT_M = 1.75


def _end_spread(centered: np.ndarray, up: np.ndarray, coords: np.ndarray, mask: np.ndarray) -> float:
    pts = centered[mask]
    if len(pts) < 8:
        return 1e9
    along = np.outer(pts @ up, up)
    return float(np.linalg.norm(pts - along, axis=1).mean())


def _stand(mesh: trimesh.Trimesh) -> None:
    vertices = np.asarray(mesh.vertices, dtype=np.float64)
    centered = vertices - vertices.mean(axis=0)
    # The body axis is the direction the figure actually extends, not the
    # nearest world axis. That keeps a leaning scan from staying diagonal.
    _, _, axes = np.linalg.svd(centered, full_matrices=False)
    up = axes[0].copy()
    side = axes[1].copy()
    coords = centered @ up
    low, high = float(coords.min()), float(coords.max())
    span = max(high - low, 1e-8)
    # On a full body the feet are the narrow end and the head sits on the
    # wider shoulders, so the wider tip points up.
    head_at_low = _end_spread(centered, up, coords, coords <= low + 0.18 * span) > _end_spread(
        centered, up, coords, coords >= high - 0.18 * span
    )
    if head_at_low:
        up = -up
    side = side / max(np.linalg.norm(side), 1e-8)
    up = up / max(np.linalg.norm(up), 1e-8)
    forward = np.cross(side, up)
    forward = forward / max(np.linalg.norm(forward), 1e-8)
    basis = np.stack([side, up, forward], axis=0)
    vertices = centered @ basis.T

    # The face, chest, and toes stick out. Turn that bulge toward +Z.
    center = (vertices.min(axis=0) + vertices.max(axis=0)) / 2.0
    if float(vertices[:, 2].mean() - center[2]) < 0:
        vertices[:, 0] *= -1.0
        vertices[:, 2] *= -1.0

    height = float(vertices[:, 1].max() - vertices[:, 1].min())
    vertices *= BODY_HEIGHT_M / max(height, 1e-8)
    vertices[:, 0] -= (vertices[:, 0].min() + vertices[:, 0].max()) / 2.0
    vertices[:, 2] -= (vertices[:, 2].min() + vertices[:, 2].max()) / 2.0
    vertices[:, 1] -= vertices[:, 1].min()
    mesh.vertices = vertices


def prepare_body(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    """Smooth a reconstruction and stand it on its feet."""
    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.to_geometry()
    mesh = mesh.copy()
    mesh.merge_vertices()
    mesh.update_faces(mesh.nondegenerate_faces())
    mesh.remove_unreferenced_vertices()
    components = mesh.split(only_watertight=False)
    if components:
        mesh = max(components, key=lambda item: len(item.faces))
    source_colors = None
    source_points = None
    if getattr(mesh.visual, "kind", None) == "vertex":
        source_colors = np.asarray(mesh.visual.vertex_colors).copy()
        source_points = np.asarray(mesh.vertices).copy()
    mesh = mesh.subdivide()
    filter_taubin(mesh, lamb=0.5, nu=0.53, iterations=20)
    if source_colors is not None and source_points is not None:
        _, nearest = cKDTree(source_points).query(mesh.vertices)
        mesh.visual.vertex_colors = source_colors[nearest]
    _stand(mesh)
    mesh.fix_normals()
    return mesh


def prepare_glb(source: str, destination: str) -> trimesh.Trimesh:
    mesh = prepare_body(trimesh.load(source, force="mesh"))
    mesh.export(destination, file_type="glb")
    return mesh
