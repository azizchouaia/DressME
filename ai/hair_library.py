"""Fit the CC0 MakeHuman hairstyles to the SMPL-X avatar and export them as skinned GLBs.

The MakeHuman hair meshes are hair cards made on the MakeHuman base body. The
base head is aligned to the avatar head (eyes, jaw, head joint, then ICP on the
skull), and each hair vertex keeps its place relative to the closest skin:
the closest point on the base body is carried over to the avatar surface, and
the hair keeps its distance from it. Long hair therefore rests on the avatar's
own shoulders and back. Skin weights come from the avatar triangle under each
vertex, so the hair follows the head and the upper body.

The textures are turned into grey strands with alpha so the viewer can tint
them with any hair colour.

    python ai/hair_library.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image
from scipy import sparse
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai"))
sys.path.insert(0, str(ROOT / "ai" / "remu"))

from garment_job import _export_faces  # noqa: E402
from pygltflib import GLTF2  # noqa: E402
from skin_garments import body_skin  # noqa: E402
from smplx_export import pack_glb, vertex_normals  # noqa: E402
from texture_samples import _pack  # noqa: E402

SOURCE = ROOT / "ai" / "assets" / "makehuman"
BODY = ROOT / "avatar_studio" / "web" / "smplx_thin.glb"
OUT = ROOT / "avatar_studio" / "web" / "hair"
BODY_VERTS = 13380
CLEARANCE = 0.0015
SIT = 0.72
CAP_LIFT = 0.0012
CAP_REACH = 0.02
CAP_REACH_FRONT = 0.006
CAP_BROW = 0.05
CAP_NAPE = 0.09
CAP_EAR_X = 0.07
CAP_ROWS = 16
CAP_GREY = 185
ANCHOR_JOINTS = ("head", "jaw", "left_eye_smplhf", "right_eye_smplhf", "neck", "spine3", "spine2", "left_collar", "right_collar")
STYLES = {
    "short01": {"label": "Mohawk", "look": "short"},
    "short02": {"label": "Quiff", "look": "short"},
    "short03": {"label": "Fringe", "look": "short"},
    "short04": {"label": "Crop", "look": "short"},
    "afro01": {"label": "Afro", "look": "curly"},
    "bob01": {"label": "Bob", "look": "bob"},
    "bob02": {"label": "Short bob", "look": "bob"},
    "long01": {"label": "Long", "look": "long"},
    "ponytail01": {"label": "Ponytail", "look": "ponytail"},
    "braid01": {"label": "Braid", "look": "braid"},
}


def read_obj(path: Path):
    """Vertices, uvs, and triangles with separate vertex and uv indices."""
    verts, uvs, tris_v, tris_t, groups = [], [], [], [], {}
    group = None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("v "):
            verts.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("vt "):
            uvs.append([float(x) for x in line.split()[1:3]])
        elif line.startswith("g "):
            group = line.split()[1]
        elif line.startswith("f "):
            corners = [token.split("/") for token in line.split()[1:]]
            v = [int(c[0]) - 1 for c in corners]
            t = [int(c[1]) - 1 if len(c) > 1 and c[1] else -1 for c in corners]
            for k in range(1, len(v) - 1):
                tris_v.append([v[0], v[k], v[k + 1]])
                tris_t.append([t[0], t[k], t[k + 1]])
                groups.setdefault(group, []).append(len(tris_v) - 1)
    return np.array(verts, dtype=np.float64), np.array(uvs, dtype=np.float64), np.array(tris_v), np.array(tris_t), groups


def _joint(verts: np.ndarray, faces: np.ndarray, groups: dict, name: str) -> np.ndarray:
    return verts[np.unique(faces[groups[name]])].mean(axis=0)


def umeyama(source: np.ndarray, target: np.ndarray):
    """Scale, rotation, translation taking source points onto target points."""
    mu_s, mu_t = source.mean(axis=0), target.mean(axis=0)
    s, t = source - mu_s, target - mu_t
    u, d, vt = np.linalg.svd(t.T @ s / len(source))
    fix = np.eye(3)
    if np.linalg.det(u @ vt) < 0:
        fix[2, 2] = -1
    rotation = u @ fix @ vt
    scale = np.trace(np.diag(d) @ fix) / s.var(axis=0).sum()
    return scale, rotation, mu_t - scale * rotation @ mu_s


def _cap_size(points: np.ndarray, eye_y: float) -> np.ndarray:
    cap = points[points[:, 1] > eye_y]
    return np.array([np.ptp(cap[:, 0]), cap[:, 1].max() - eye_y, np.ptp(cap[:, 2])])


def align_heads(mh_verts, mh_faces, mh_groups, positions, names, world, head_mask):
    """MakeHuman and SMPL-X place their jaw joints differently, so only the
    eyes are shared landmarks; scale comes from the skull cap above the eyes
    and ICP stays rigid so it cannot shrink the head into the face."""
    eyes_mh = (_joint(mh_verts, mh_faces, mh_groups, "joint-l-eye") + _joint(mh_verts, mh_faces, mh_groups, "joint-r-eye")) / 2
    eyes_sx = (world[names.index("left_eye_smplhf")] + world[names.index("right_eye_smplhf")]) / 2
    body = mh_verts[:BODY_VERTS]
    target = positions[head_mask]
    near_mh = np.abs(body[:, 2] - eyes_mh[2]) < 4.0
    scale = float(np.mean(_cap_size(target, eyes_sx[1]) / _cap_size(body[near_mh], eyes_mh[1])))
    rotation = np.eye(3)
    shift = eyes_sx - scale * eyes_mh
    aligned = scale * body @ rotation.T + shift
    tree = cKDTree(target)
    skull = (aligned[:, 1] > eyes_sx[1] - 0.03) & (np.linalg.norm(aligned - eyes_sx, axis=1) < 0.16)
    for _ in range(30):
        _, nearest = tree.query(aligned[skull])
        _, step_rotation, _ = umeyama(aligned[skull], target[nearest])
        step_shift = target[nearest].mean(axis=0) - step_rotation @ aligned[skull].mean(axis=0)
        aligned = aligned @ step_rotation.T + step_shift
        rotation, shift = step_rotation @ rotation, step_rotation @ shift + step_shift
    print("head scale", round(scale, 4), "fit error", round(float(tree.query(aligned[skull])[0].mean()), 4))
    return scale, rotation, shift


def _smooth(field: np.ndarray, faces: np.ndarray, rounds: int) -> np.ndarray:
    edges = np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]])
    edges = np.concatenate([edges, edges[:, ::-1]])
    adjacency = sparse.csr_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(len(field), len(field)))
    adjacency.data[:] = 1.0
    degree = np.asarray(adjacency.sum(axis=1)).ravel()
    out = field.copy()
    for _ in range(rounds):
        out = 0.5 * out + 0.5 * (adjacency @ out) / np.maximum(degree, 1)[:, None]
    return out


def _in_face(points: np.ndarray, eyes_y: float, eyes_z: float) -> np.ndarray:
    """Hair cards in front of the eyes, nose, mouth or throat. MakeHuman fringes
    and side locks land there on the SMPL-X face proportions."""
    x, y, z = points[:, 0], points[:, 1], points[:, 2]
    face = (np.abs(x) < 0.055) & (y > eyes_y - 0.12) & (y < eyes_y + 0.012) & (z > eyes_z - 0.04)
    throat = (np.abs(x) < 0.045) & (y > eyes_y - 0.2) & (y <= eyes_y - 0.12) & (z > eyes_z - 0.09)
    return face | throat


def _grow(mask: np.ndarray, faces: np.ndarray, rounds: int, grow: bool) -> np.ndarray:
    out = mask.copy()
    for _ in range(rounds):
        hit = out[faces]
        touched = np.zeros_like(out)
        if grow:
            touched[faces[hit.any(axis=1)].ravel()] = True
            out = out | touched
        else:
            touched[faces[~hit.all(axis=1)].ravel()] = True
            out = out & ~touched
    return out


def scalp_cap(positions, faces, normals, head_mask, hair_mesh, eyes_y, eyes_z):
    """Avatar head triangles under the hair, so gaps between cards show hair
    colour instead of skin. The face stays clear: in front of the ears the cap
    starts above the brows."""
    y, z = positions[:, 1], positions[:, 2]
    forehead = z > eyes_z - 0.035
    ears = (np.abs(positions[:, 0]) > CAP_EAR_X) & (y < eyes_y + 0.03)
    allowed = head_mask & ~ears & np.where(forehead, y > eyes_y + CAP_BROW, y > eyes_y - CAP_NAPE)
    # The strands are transparent between cards. The cap is every scalp triangle the hair should hide, not only the ones touching a strand.
    picked = faces[allowed[faces].all(axis=1)]
    used = np.unique(picked)
    remap = np.full(len(positions), -1)
    remap[used] = np.arange(len(used))
    return used, remap[picked]


def strands(path: Path) -> Image.Image:
    """Grey strands with alpha, mean brightness about 0.8 so a tint reads true."""
    image = np.asarray(Image.open(path).convert("RGBA")).astype(np.float32)
    alpha = image[..., 3]
    light = image[..., :3] @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    seen = alpha > 127
    mean = float(light[seen].mean()) if seen.any() else 128.0
    grey = np.clip(light * (205.0 / max(mean, 1.0)), 0, 255)
    out = np.dstack([grey, grey, grey, alpha]).astype(np.uint8)
    return Image.fromarray(out)


def build() -> list[dict]:
    positions, joints, weights, names, parents, world = body_skin(BODY)
    gltf = GLTF2().load(str(BODY))
    faces = _export_faces(gltf, gltf.binary_blob(), gltf.meshes[0].primitives[0].indices)
    dominant = joints[np.arange(len(joints)), weights.argmax(axis=1)]
    head_mask = np.isin(dominant, [names.index(n) for n in ("head", "jaw", "left_eye_smplhf", "right_eye_smplhf")])
    anchor_mask = np.isin(dominant, [names.index(n) for n in ANCHOR_JOINTS])
    anchor_faces = faces[anchor_mask[faces].all(axis=1)]
    avatar_anchor = trimesh.Trimesh(positions, anchor_faces, process=False)
    avatar_head = trimesh.Trimesh(positions, faces[head_mask[faces].all(axis=1)], process=False)
    avatar_normals = vertex_normals(positions, faces)

    mh_verts, _, mh_faces, _, mh_groups = read_obj(SOURCE / "base.obj")
    scale, rotation, shift = align_heads(mh_verts, mh_faces, mh_groups, positions, names, world, head_mask)
    mh_body = scale * mh_verts @ rotation.T + shift
    body_faces = mh_faces[(mh_faces < BODY_VERTS).all(axis=1)]
    _, nearest = cKDTree(positions).query(mh_body[:BODY_VERTS])
    close = np.linalg.norm(mh_body[:BODY_VERTS] - positions[nearest], axis=1) < 0.04
    usable = close & anchor_mask[nearest]
    mh_anchor = trimesh.Trimesh(mh_body[:BODY_VERTS], body_faces[usable[body_faces].all(axis=1)], process=False)

    eyes = (world[names.index("left_eye_smplhf")] + world[names.index("right_eye_smplhf")]) / 2
    eyes_y, eyes_z = float(eyes[1]), float(eyes[2])
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    for style, info in STYLES.items():
        folder = SOURCE / "hair" / style
        verts, uvs, tris_v, tris_t, _ = read_obj(folder / f"{style}.obj")
        hair = scale * verts @ rotation.T + shift
        on_base, _, _ = trimesh.proximity.closest_point(mh_anchor, hair)
        on_avatar, _, _ = trimesh.proximity.closest_point(avatar_anchor, on_base)
        moved = hair + _smooth(on_avatar - on_base, tris_v, 8)
        closest, _, tri = trimesh.proximity.closest_point(avatar_head, moved)
        offset = moved - closest
        moved = closest + offset * SIT
        depth = np.einsum("ij,ij->i", moved - closest, avatar_head.face_normals[tri])
        sunk = depth < CLEARANCE
        moved[sunk] = closest[sunk] + avatar_head.face_normals[tri[sunk]] * CLEARANCE

        closest, _, tri = trimesh.proximity.closest_point(avatar_anchor, moved)
        corners = avatar_anchor.faces[tri]
        bary = np.clip(trimesh.triangles.points_to_barycentric(positions[corners], closest), 0, None)
        bary /= np.maximum(bary.sum(axis=1, keepdims=True), 1e-8)
        dense = np.zeros((len(moved), len(names)), dtype=np.float32)
        rows = np.arange(len(moved))
        for corner in range(3):
            for slot in range(joints.shape[1]):
                np.add.at(dense, (rows, joints[corners[:, corner], slot]), bary[:, corner] * weights[corners[:, corner], slot])
        order = np.argsort(-dense, axis=1)[:, :4]
        picked = np.take_along_axis(dense, order, axis=1)
        picked /= np.maximum(picked.sum(axis=1, keepdims=True), 1e-8)

        clear = ~(_in_face(moved, eyes_y, eyes_z)[tris_v].any(axis=1))
        tris_v, tris_t = tris_v[clear], tris_t[clear]
        pairs, inverse = np.unique(np.stack([tris_v.ravel(), tris_t.ravel()], axis=1), axis=0, return_inverse=True)
        split_faces = inverse.reshape(tris_v.shape)
        cloth = moved[pairs[:, 0]].astype(np.float32)
        uv = uvs[pairs[:, 1]].astype(np.float32)
        uv[:, 1] = 1.0 - uv[:, 1]
        joint_ids = order[pairs[:, 0]]
        joint_weights = picked[pairs[:, 0]]

        cap_verts, cap_faces = scalp_cap(positions, faces, avatar_normals, head_mask, trimesh.Trimesh(moved, tris_v, process=False), eyes_y, eyes_z)
        image = strands(next(folder.glob("*_diffuse.png")))
        height = image.height
        uv[:, 1] *= height / (height + CAP_ROWS)
        padded = Image.new("RGBA", (image.width, height + CAP_ROWS), (CAP_GREY, CAP_GREY, CAP_GREY, 255))
        padded.paste(image, (0, 0))
        cap_uv = np.tile([0.5, (height + CAP_ROWS / 2) / (height + CAP_ROWS)], (len(cap_verts), 1)).astype(np.float32)
        top = np.argsort(-weights[cap_verts], axis=1)[:, :4]
        cap_joints = np.take_along_axis(joints[cap_verts], top, axis=1)
        cap_weights = np.take_along_axis(weights[cap_verts], top, axis=1)
        cap_weights = cap_weights / np.maximum(cap_weights.sum(axis=1, keepdims=True), 1e-8)
        if cap_joints.shape[1] < 4:
            fill = 4 - cap_joints.shape[1]
            cap_joints = np.pad(cap_joints, ((0, 0), (0, fill)))
            cap_weights = np.pad(cap_weights, ((0, 0), (0, fill)))
        cap_points = positions[cap_verts] + avatar_normals[cap_verts] * CAP_LIFT

        all_verts = np.concatenate([cloth, cap_points]).astype(np.float32)
        all_faces = np.concatenate([split_faces, cap_faces + len(cloth)])
        all_uv = np.concatenate([uv, cap_uv]).astype(np.float32)
        all_joints = np.concatenate([joint_ids, cap_joints]).astype(np.uint16)
        all_weights = np.concatenate([joint_weights, cap_weights]).astype(np.float32)
        normals = vertex_normals(all_verts, all_faces)
        path = OUT / f"{style}.glb"
        pack_glb(all_verts, normals, all_joints, all_weights, all_faces, names, parents, world, path)
        _pack(path, padded, 0, uvs=all_uv, normals=normals, roughness=0.55)
        manifest.append({"id": style, "label": info["label"], "look": info["look"], "url": f"/hair/{style}.glb", "license": "CC0, MakeHuman system assets"})
        print(style, len(cloth), "vertices", path.stat().st_size, "bytes")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    build()
