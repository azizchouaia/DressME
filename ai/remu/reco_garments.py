"""Turn a SiTH outfit reconstruction into a shirt and pants that the avatar wears.

The reconstruction and the SMPL-X body fitted to the photo share SiTH's image
frame (u = 512 + 512 x, v = 512 - 512 y). Each vertex takes its garment label
from the photo it faces, the mesh is cut into the top and the bottom, and every
piece is moved from the fitted body onto the avatar triangle by triangle: both
bodies have the SMPL-X topology, so a point keeps its triangle, barycentric
position, and distance from the skin. The texture is the photos themselves.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import fast_simplification
import numpy as np
import trimesh
from PIL import Image
from scipy import ndimage, sparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))
sys.path.insert(0, str(ROOT / "ai" / "remu"))

from garment_job import _export_faces  # noqa: E402
from pygltflib import GLTF2  # noqa: E402
from skin_garments import body_skin  # noqa: E402
from smplx_export import pack_glb, vertex_normals  # noqa: E402
from texture_samples import _pack  # noqa: E402
from vision_fit import PANTS, SKIRT, UPPER  # noqa: E402

WEB = ROOT / "avatar_studio" / "web"
BODY = WEB / "smplx_thin.glb"
OUT = WEB / "garments" / "saved" / "reco"
SIDE = 1024
OTHER, TOP, BOTTOM = 0, 1, 2
DRESS = 7
CLEARANCE = 0.004
LOOSEST = 0.09
OVERLAP_RINGS = 2
OVERLAP_LIFT = 0.002
FACE_BUDGET = 90000
HEM_LIFT = 0.03
HEM_SNAP = 0.012
HEM_MIN_PART = 0.05
BARE = ("head", "jaw", "eye", "foot", "thumb", "index", "middle", "ring", "pinky")


def _raw_classes(labels: np.ndarray) -> np.ndarray:
    out = np.full(labels.shape, OTHER, dtype=np.uint8)
    out[np.isin(labels, (UPPER, DRESS))] = TOP
    out[np.isin(labels, (PANTS, SKIRT))] = BOTTOM
    return out


def _classes(labels: np.ndarray) -> np.ndarray:
    """Garment class per pixel, background filled with the nearest person pixel."""
    out = _raw_classes(labels)
    empty = labels == 0
    if empty.any() and (~empty).any():
        _, (rows, cols) = ndimage.distance_transform_edt(empty, return_indices=True)
        out = out[rows, cols]
    return out


def _pixels(points: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    cols = np.clip(np.round(SIDE / 2 + SIDE / 2 * points[:, 0]), 0, SIDE - 1).astype(int)
    rows = np.clip(np.round(SIDE / 2 - SIDE / 2 * points[:, 1]), 0, SIDE - 1).astype(int)
    return rows, cols


def _adjacency(faces: np.ndarray, count: int) -> sparse.csr_matrix:
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = np.concatenate([edges, edges[:, ::-1]])
    return sparse.csr_matrix((np.ones(len(edges), dtype=np.float32), (edges[:, 0], edges[:, 1])), shape=(count, count))


def label_vertices(verts: np.ndarray, normals: np.ndarray, faces: np.ndarray, front: np.ndarray, back: np.ndarray) -> np.ndarray:
    rows, cols = _pixels(verts)
    seen_front = front[rows, cols]
    seen_back = back[rows, SIDE - 1 - cols]
    labels = np.where(normals[:, 2] >= 0, seen_front, seen_back)
    side = np.abs(normals[:, 2]) < 0.25
    labels[side] = np.where(seen_front[side] != OTHER, seen_front[side], seen_back[side])
    adjacency = _adjacency(faces, len(verts))
    votes = np.eye(3, dtype=np.float32)[labels]
    for _ in range(6):
        votes = adjacency @ votes + votes
        votes /= votes.sum(axis=1, keepdims=True)
    return votes.argmax(axis=1).astype(np.uint8)


def _grow(chosen: np.ndarray, into: np.ndarray, adjacency: sparse.csr_matrix, rings: int) -> np.ndarray:
    grown = chosen.copy()
    for _ in range(rings):
        grown |= (adjacency @ grown.astype(np.float32) > 0) & into
    return grown


def _largest(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    parts = mesh.split(only_watertight=False)
    if not len(parts):
        raise RuntimeError("That garment has no surface in the reconstruction.")
    return max(parts, key=lambda part: len(part.faces))


def cut_pieces(reco: trimesh.Trimesh, labels: np.ndarray) -> dict[str, tuple[trimesh.Trimesh, np.ndarray]]:
    """Shirt and pants meshes, each with a per-vertex flag for the overlap band."""
    faces = np.asarray(reco.faces)
    adjacency = _adjacency(faces, len(reco.vertices))
    top = labels == TOP
    bottom = labels == BOTTOM
    top_grown = _grow(top, bottom, adjacency, OVERLAP_RINGS)
    query = trimesh.proximity.ProximityQuery(reco)
    pieces = {}
    for name, chosen, band in (("shirt", top_grown, top_grown & ~top), ("pants", bottom, np.zeros_like(bottom))):
        keep = chosen[faces].all(axis=1)
        if keep.sum() < 200:
            raise RuntimeError(f"The {name} was not found on the reconstruction.")
        part = _largest(reco.submesh([np.nonzero(keep)[0]], append=True, repair=False))
        _, nearest = query.vertex(part.vertices)
        pieces[name] = (part, band[nearest])
    return pieces


def _smooth(values: np.ndarray, faces: np.ndarray, rounds: int) -> np.ndarray:
    adjacency = _adjacency(faces, len(values))
    degree = np.asarray(adjacency.sum(axis=1)).ravel()
    out = values.astype(np.float64)
    for _ in range(rounds):
        out = 0.5 * out + 0.5 * (adjacency @ out) / np.maximum(degree, 1)
    return out


def _bary_normals(normals: np.ndarray, faces: np.ndarray, tri: np.ndarray, bary: np.ndarray) -> np.ndarray:
    picked = (normals[faces[tri]] * bary[:, :, None]).sum(axis=1)
    return picked / np.maximum(np.linalg.norm(picked, axis=1, keepdims=True), 1e-8)


def retarget(piece: trimesh.Trimesh, band: np.ndarray, fitted: trimesh.Trimesh, avatar: np.ndarray, avatar_faces: np.ndarray):
    """Move a piece from the fitted body onto the avatar. Returns vertices, triangles, barycentrics."""
    points = np.asarray(piece.vertices)
    closest, _, tri = trimesh.proximity.closest_point(fitted, points)
    bary = trimesh.triangles.points_to_barycentric(fitted.triangles[tri], closest)
    bary = np.clip(bary, 0, None)
    bary /= np.maximum(bary.sum(axis=1, keepdims=True), 1e-8)
    fitted_normals = _bary_normals(np.asarray(fitted.vertex_normals), np.asarray(fitted.faces), tri, bary)
    scale = float(np.ptp(avatar[:, 1]) / np.ptp(np.asarray(fitted.vertices)[:, 1]))
    offset = np.einsum("ij,ij->i", points - closest, fitted_normals) * scale
    offset = _smooth(np.clip(offset, CLEARANCE, LOOSEST), np.asarray(piece.faces), 4)
    offset = np.clip(offset, CLEARANCE, LOOSEST) + band * OVERLAP_LIFT
    avatar_normals = vertex_normals(avatar, avatar_faces)
    anchor = (avatar[avatar_faces[tri]] * bary[:, :, None]).sum(axis=1)
    moved = anchor + _bary_normals(avatar_normals, avatar_faces, tri, bary) * offset[:, None]
    return moved.astype(np.float32), tri, bary


def push_out(points: np.ndarray, avatar: trimesh.Trimesh, clearance: float) -> np.ndarray:
    closest, _, tri = trimesh.proximity.closest_point(avatar, points)
    normals = avatar.face_normals[tri]
    depth = np.einsum("ij,ij->i", points - closest, normals)
    inside = depth < clearance
    points = points.copy()
    points[inside] = closest[inside] + normals[inside] * clearance
    return points


def skin(tri: np.ndarray, bary: np.ndarray, faces: np.ndarray, joints: np.ndarray, weights: np.ndarray, count: int):
    dense = np.zeros((len(tri), count), dtype=np.float32)
    rows = np.arange(len(tri))
    for corner in range(3):
        vertex = faces[tri, corner]
        for slot in range(joints.shape[1]):
            np.add.at(dense, (rows, joints[vertex, slot]), bary[:, corner] * weights[vertex, slot])
    order = np.argsort(-dense, axis=1)[:, :4]
    picked = np.take_along_axis(dense, order, axis=1)
    picked /= np.maximum(picked.sum(axis=1, keepdims=True), 1e-8)
    return order.astype(np.uint16), picked.astype(np.float32)


def _filled(image: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Every pixel takes the colour of the nearest garment pixel, away from the cut-out edge."""
    inner = ndimage.binary_erosion(mask, iterations=4)
    if inner.sum() > 0.5 * mask.sum():
        mask = inner
    if not mask.any():
        return image
    _, (rows, cols) = ndimage.distance_transform_edt(~mask, return_indices=True)
    return image[rows, cols]


def photo_uvs(source: np.ndarray, faces: np.ndarray):
    """Split vertices where front and back faces meet; uv into a front | back atlas."""
    triangles = source[faces]
    face_z = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])[:, 2]
    back = face_z < 0
    key = faces * 2 + back[:, None]
    unique, inverse = np.unique(key.ravel(), return_inverse=True)
    vertex = unique // 2
    on_back = (unique % 2).astype(bool)
    rows, cols = _pixels(source[vertex])
    uvs = np.zeros((len(unique), 2), dtype=np.float32)
    uvs[:, 0] = np.where(on_back, 0.5 + (SIDE - 1 - cols + 0.5) / (2 * SIDE), (cols + 0.5) / (2 * SIDE))
    uvs[:, 1] = (rows + 0.5) / SIDE
    return vertex, inverse.reshape(faces.shape), uvs


def atlas(front_rgb: np.ndarray, back_rgb: np.ndarray, front_cls: np.ndarray, back_cls: np.ndarray, piece_class: int) -> Image.Image:
    left = _filled(front_rgb, front_cls == piece_class)
    right = _filled(back_rgb, back_cls == piece_class)
    return Image.fromarray(np.concatenate([left, right], axis=1))


def hem(points: np.ndarray, faces: np.ndarray, height: float) -> tuple[np.ndarray, np.ndarray]:
    """Cut the trouser legs straight above the ankles. The reconstruction runs
    the cloth over the shoes and the floor; below the cut it is not cloth.
    Open edges near the cut are snapped onto it so the hem is a clean line."""
    faces = faces[(points[faces, 1] >= height).all(axis=1)]
    mesh = trimesh.Trimesh(points, faces, process=False)
    part = trimesh.graph.connected_component_labels(mesh.face_adjacency, node_count=len(faces))
    sizes = np.bincount(part)
    faces = faces[sizes[part] >= HEM_MIN_PART * sizes.max()]
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    rim = np.unique(unique[counts == 1])
    points = points.copy()
    low = rim[points[rim, 1] < height + HEM_SNAP]
    points[low, 1] = height
    return points, faces


def build(run: Path, dataset: Path, out: Path = OUT) -> dict:
    reco = trimesh.load(run / "outfit_reco.obj", process=False, force="mesh")
    fitted = trimesh.load(run / "outfit_smplx.obj", process=False, force="mesh")
    verts, faces = np.asarray(reco.vertices, dtype=np.float32), np.asarray(reco.faces)
    if len(faces) > FACE_BUDGET:
        verts, faces = fast_simplification.simplify(verts, faces, target_reduction=1 - FACE_BUDGET / len(faces))
    reco = trimesh.Trimesh(verts, faces, process=True)
    front_raw = np.load(dataset / "labels" / "front.npy")
    back_raw = np.load(dataset / "labels" / "back.npy")
    front_cls, back_cls = _classes(front_raw), _classes(back_raw)
    labels = label_vertices(np.asarray(reco.vertices), np.asarray(reco.vertex_normals), np.asarray(reco.faces), front_cls, back_cls)
    front_rgb = np.asarray(Image.open(dataset / "images" / "outfit.png").convert("RGB"))
    back_rgb = np.asarray(Image.open(dataset / "back_images" / "outfit.png").convert("RGB"))

    positions, joints, weights, names, parents, world = body_skin(BODY)
    gltf = GLTF2().load(str(BODY))
    avatar_faces = _export_faces(gltf, gltf.binary_blob(), gltf.meshes[0].primitives[0].indices)
    avatar_mesh = trimesh.Trimesh(positions, avatar_faces, process=False)
    bare = [index for index, bone in enumerate(names) if any(part in bone for part in BARE)]
    out.mkdir(parents=True, exist_ok=True)
    report = {"labels": {name: int((labels == value).sum()) for name, value in (("other", OTHER), ("top", TOP), ("bottom", BOTTOM))}}
    for name, (piece, band) in cut_pieces(reco, labels).items():
        source = np.asarray(piece.vertices, dtype=np.float32)
        piece_faces = np.asarray(piece.faces)
        moved, tri, bary = retarget(piece, band, fitted, positions, avatar_faces)
        moved = push_out(moved, avatar_mesh, CLEARANCE)
        piece_joints, piece_weights = skin(tri, bary, avatar_faces, joints, weights, len(names))
        on_skin = np.isin(piece_joints[:, 0], bare) & (piece_weights[:, 0] > 0.5)
        piece_faces = piece_faces[~on_skin[piece_faces].any(axis=1)]
        if name == "pants":
            moved, piece_faces = hem(moved, piece_faces, world[[names.index("left_ankle"), names.index("right_ankle")], 1].max() + HEM_LIFT)
        if len(piece_faces) < 200:
            raise RuntimeError(f"The {name} sits on the head, hands, or feet only.")
        vertex, split_faces, uvs = photo_uvs(source, piece_faces)
        cloth = moved[vertex]
        path = out / f"{name}.glb"
        pack_glb(cloth, vertex_normals(cloth, split_faces), piece_joints[vertex], piece_weights[vertex], split_faces, names, parents, world, path)
        piece_class = TOP if name == "shirt" else BOTTOM
        _pack(path, atlas(front_rgb, back_rgb, _raw_classes(front_raw), _raw_classes(back_raw), piece_class), 0, uvs=uvs)
        report[name] = {"vertices": int(len(cloth)), "faces": int(len(split_faces)), "bytes": path.stat().st_size}
    (out / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(build(Path(sys.argv[1]), Path(sys.argv[2])), indent=2))
