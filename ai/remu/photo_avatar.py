"""Give the avatar the person's face, hair colour, and one skin tone from their photos.

This runs once per person, after a Kaggle run has fitted SMPL-X to the front
photo. The fitted body has the avatar's topology, so each avatar vertex knows
where it sits in the photos. Only the face keeps photo pixels, beard included;
the rest of the body, hands and feet included, gets a single skin tone
measured on the face, so nothing that shows through clothes has another
colour. Hair comes from the 3D style library instead of paint; the style
picked by hair_look.py is stored in the profile.
The geometry and skeleton stay those of smplx_thin, so every garment fitted to
smplx_thin fits this avatar too.

    python ai/remu/photo_avatar.py RUN_DIR DATASET_DIR NAME
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image
from scipy import ndimage

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))
sys.path.insert(0, str(ROOT / "ai" / "remu"))

from garment_job import _export_faces  # noqa: E402
from pygltflib import GLTF2  # noqa: E402
from reco_garments import BODY, photo_uvs  # noqa: E402
from skin_garments import body_skin  # noqa: E402
from smplx_export import pack_glb, vertex_normals  # noqa: E402
from texture_samples import _pack  # noqa: E402
from vision_fit import FACE, HAIR  # noqa: E402

AVATARS = ROOT / "avatar_studio" / "web" / "avatars"
FEATHER = 5
CHIN, CHIN_FADE = 0.5, 0.2


def skin_tone(image: np.ndarray, labels: np.ndarray) -> np.ndarray:
    """Median face colour, leaving out beard, brows, eyes, and highlights."""
    face = image[ndimage.binary_erosion(labels == FACE, iterations=3)].astype(np.float32)
    if len(face) < 200:
        raise RuntimeError("The front photo shows too little of the face to read the skin tone.")
    light = face @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    low, high = np.percentile(light, [45, 92])
    return np.median(face[(light >= low) & (light <= high)], axis=0)


def hair_tone(image: np.ndarray, labels: np.ndarray, fallback: np.ndarray) -> np.ndarray:
    hair = image[labels == HAIR]
    return np.median(hair, axis=0).astype(np.float32) if len(hair) > 100 else fallback * 0.35


def face_rows(dataset: Path) -> tuple[float, float] | None:
    """Image rows of the nose tip and the chin. The chin sits part way from
    the nose keypoint to the neck keypoint; below it the face label is neck."""
    path = dataset / "images" / "outfit_keypoints.json"
    if not path.exists():
        return None
    people = json.loads(path.read_text(encoding="utf-8")).get("people") or []
    if not people:
        return None
    points = np.asarray(people[0]["pose_keypoints_2d"], dtype=np.float32).reshape(-1, 3)
    nose, neck = points[0], points[1]
    if min(nose[2], neck[2]) < 0.3 or neck[1] <= nose[1]:
        return None
    return float(nose[1]), float(nose[1] + CHIN * (neck[1] - nose[1]))


def look(dataset: Path) -> dict:
    path = dataset / "labels" / "look.json"
    if not path.exists():
        return {}
    picks = json.loads(path.read_text(encoding="utf-8"))
    return {"hair": picks.get("hair", "none")}


def _side(image: np.ndarray, labels: np.ndarray, skin: np.ndarray, rows: tuple[float, float] | None) -> np.ndarray:
    """Skin tone everywhere, the whole face printed from the photo, beard
    included. Hair above the nose is left to the 3D hairstyle, and the neck
    below the chin stays skin. The print fades into the skin tone at its edge
    so the face has no cut-out border."""
    face = labels == FACE
    fade = np.ones(labels.shape, dtype=np.float32)
    if rows is not None:
        nose, chin = rows
        row = np.arange(labels.shape[0])[:, None]
        beard = (labels == HAIR) & (row > nose)
        face = face | ndimage.binary_opening(beard, iterations=2)
        span = max(chin - nose, 1.0)
        fade = np.clip((chin - row) / (CHIN_FADE * span), 0, 1) * np.ones(labels.shape, dtype=np.float32)
    out = np.empty(image.shape, dtype=np.float32)
    out[:] = skin
    if face.sum() < 200:
        return out.astype(np.uint8)
    inner = ndimage.binary_erosion(face, iterations=4)
    weight = np.clip(ndimage.gaussian_filter(inner.astype(np.float32), FEATHER) * 2.0, 0, 1) * ndimage.binary_dilation(inner, iterations=FEATHER)
    weight = (weight * fade)[..., None]
    return np.clip(out * (1 - weight) + image.astype(np.float32) * weight, 0, 255).astype(np.uint8)


def build(run: Path, dataset: Path, name: str) -> dict:
    fitted = trimesh.load(run / "outfit_smplx.obj", process=False, force="mesh")
    front = np.asarray(Image.open(dataset / "images" / "outfit.png").convert("RGB"))
    back = np.asarray(Image.open(dataset / "back_images" / "outfit.png").convert("RGB"))
    front_labels = np.load(dataset / "labels" / "front.npy")
    back_labels = np.load(dataset / "labels" / "back.npy")
    skin = skin_tone(front, front_labels)
    hair = hair_tone(back, back_labels, skin)
    positions, joints, weights, names, parents, world = body_skin(BODY)
    gltf = GLTF2().load(str(BODY))
    faces = _export_faces(gltf, gltf.binary_blob(), gltf.meshes[0].primitives[0].indices)
    if len(fitted.vertices) != len(positions):
        raise RuntimeError("The fitted body does not have the avatar's SMPL-X topology.")
    vertex, split_faces, uvs = photo_uvs(np.asarray(fitted.vertices, dtype=np.float32), faces)
    normals = vertex_normals(positions, faces)[vertex]
    plain = np.empty_like(back)
    plain[:] = skin.astype(np.uint8)
    atlas = Image.fromarray(np.concatenate([_side(front, front_labels, skin, face_rows(dataset)), plain], axis=1))

    out = AVATARS / name
    out.mkdir(parents=True, exist_ok=True)
    path = out / "avatar.glb"
    pack_glb(positions[vertex], normals, joints[vertex], weights[vertex], split_faces, names, parents, world, path)
    _pack(path, atlas, 0, uvs=uvs, normals=normals, roughness=0.6)
    profile = {
        "name": name,
        "mesh": f"/avatars/{name}/avatar.glb",
        "skin": "#%02x%02x%02x" % tuple(int(c) for c in skin),
        "hair": "#%02x%02x%02x" % tuple(int(c) for c in hair),
        "body": BODY.name,
        "look": look(dataset),
    }
    (out / "profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
    atlas.save(out / "skin.png")
    return profile


if __name__ == "__main__":
    print(json.dumps(build(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]), indent=2))
