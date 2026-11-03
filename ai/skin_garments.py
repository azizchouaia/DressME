"""Bind the fitted garments to the same SMPL-X skeleton as the body.

Each garment vertex copies the skin weights of the nearest body vertex, so the
shirt, shorts, and vest bend with the pose instead of staying in place.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh
from pygltflib import GLTF2
from scipy.spatial import cKDTree

from smplx_export import pack_glb, vertex_normals

ROOT = Path(__file__).resolve().parents[1]
BODY = ROOT / "avatar_studio" / "web" / "smplx_thin.glb"
GARMENTS = {
    "shirt": ROOT / "avatar_studio" / "web" / "garments" / "shirt.glb",
    "shorts": ROOT / "avatar_studio" / "web" / "garments" / "shorts.glb",
    "vest": ROOT / "avatar_studio" / "web" / "garments" / "vest.glb",
}
FITTED = {
    "shirt": ROOT / "avatar_studio" / "web" / "garments" / "fitted" / "shirt.obj",
    "shorts": ROOT / "avatar_studio" / "web" / "garments" / "fitted" / "shorts.obj",
    "vest": ROOT / "avatar_studio" / "web" / "garments" / "fitted" / "vest.obj",
}


def _accessor(gltf: GLTF2, blob: bytes, index: int) -> np.ndarray:
    accessor = gltf.accessors[index]
    view = gltf.bufferViews[accessor.bufferView]
    offset = (view.byteOffset or 0) + (accessor.byteOffset or 0)
    components = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}[accessor.type]
    dtype = {5126: np.float32, 5123: np.uint16, 5125: np.uint32, 5121: np.uint8}[accessor.componentType]
    count = accessor.count * components
    data = np.frombuffer(blob, dtype=dtype, count=count, offset=offset).copy()
    return data.reshape(accessor.count, components) if components > 1 else data


def body_skin(path: Path):
    gltf = GLTF2().load(str(path))
    blob = gltf.binary_blob()
    primitive = gltf.meshes[0].primitives[0]
    positions = _accessor(gltf, blob, primitive.attributes.POSITION).astype(np.float32)
    joints = _accessor(gltf, blob, primitive.attributes.JOINTS_0).astype(np.uint16)
    weights = _accessor(gltf, blob, primitive.attributes.WEIGHTS_0).astype(np.float32)
    skin = gltf.skins[0]
    joint_nodes = list(skin.joints)
    names = [gltf.nodes[node].name for node in joint_nodes]
    index_of = {node: index for index, node in enumerate(joint_nodes)}
    parents = np.full(len(joint_nodes), -1, dtype=int)
    for node_index, node in enumerate(gltf.nodes):
        if node_index not in index_of or not node.children:
            continue
        for child in node.children:
            if child in index_of:
                parents[index_of[child]] = index_of[node_index]
    local = np.zeros((len(joint_nodes), 3), dtype=np.float64)
    for index, node_index in enumerate(joint_nodes):
        translation = gltf.nodes[node_index].translation
        if translation:
            local[index] = translation
    world = np.zeros_like(local)
    for index in range(len(joint_nodes)):
        parent = parents[index]
        world[index] = local[index] if parent < 0 else world[parent] + local[index]
    return positions, joints, weights, names, parents, world.astype(np.float32)


def main() -> None:
    positions, joints, weights, names, parents, world = body_skin(BODY)
    tree = cKDTree(positions)
    for name, path in GARMENTS.items():
        loaded = trimesh.load(FITTED[name], process=False)
        if isinstance(loaded, trimesh.Scene):
            loaded = trimesh.util.concatenate(tuple(loaded.geometry.values()))
        garment = np.asarray(loaded.vertices, dtype=np.float32)
        _, nearest = tree.query(garment, k=1)
        garment_joints = joints[nearest]
        garment_weights = weights[nearest]
        garment_weights /= np.maximum(garment_weights.sum(axis=1, keepdims=True), 1e-8)
        faces = np.asarray(loaded.faces, dtype=np.int64)
        pack_glb(
            garment,
            vertex_normals(garment, faces),
            garment_joints,
            garment_weights.astype(np.float32),
            faces,
            names,
            parents,
            world,
            path,
        )
        print(f"{name}: {len(garment)} vertices bound to {len(names)} joints")


if __name__ == "__main__":
    main()
