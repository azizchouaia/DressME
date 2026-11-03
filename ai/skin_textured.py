"""Skin the baked garments and keep their photo color and fabric normal maps."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from pygltflib import (
    ARRAY_BUFFER,
    ELEMENT_ARRAY_BUFFER,
    FLOAT,
    UNSIGNED_INT,
    UNSIGNED_SHORT,
    Accessor,
    Asset,
    Attributes,
    Buffer,
    BufferView,
    GLTF2,
    Image,
    Material,
    Mesh,
    Node,
    NormalMaterialTexture,
    PbrMetallicRoughness,
    Primitive,
    Sampler,
    Scene,
    Skin,
    Texture,
    TextureInfo,
)
from scipy.spatial import cKDTree

from skin_garments import BODY, body_skin
from smplx_export import vertex_normals

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "avatar_studio" / "web" / "garments" / "textured"
OUT = {
    "shirt": ROOT / "avatar_studio" / "web" / "garments" / "shirt.glb",
    "shorts": ROOT / "avatar_studio" / "web" / "garments" / "shorts.glb",
    "vest": ROOT / "avatar_studio" / "web" / "garments" / "vest.glb",
    "shoes": ROOT / "avatar_studio" / "web" / "garments" / "shoes.glb",
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
    return np.asarray(vertices, dtype=np.float32), np.asarray(uvs, dtype=np.float32), faces


def pack(name: str, destination: Path, names, parents, world, body_positions, body_joints, body_weights) -> None:
    vertices, uvs, corners = parse_obj(SRC / f"{name}.obj")
    tree = cKDTree(body_positions)
    _, nearest = tree.query(vertices, k=1)
    welded_joints = body_joints[nearest]
    welded_weights = body_weights[nearest]
    welded_weights /= np.maximum(welded_weights.sum(axis=1, keepdims=True), 1e-8)

    lookup = {}
    out_vertices = []
    out_uvs = []
    out_joints = []
    out_weights = []
    faces = []
    for face in corners:
        indexed = []
        for point, tex in face:
            key = (point, tex)
            index = lookup.get(key)
            if index is None:
                index = len(out_vertices)
                lookup[key] = index
                out_vertices.append(vertices[point])
                u, v = uvs[tex]
                out_uvs.append([u, 1.0 - v])
                out_joints.append(welded_joints[point])
                out_weights.append(welded_weights[point])
            indexed.append(index)
        faces.append(indexed)

    positions = np.asarray(out_vertices, dtype=np.float32)
    texcoords = np.asarray(out_uvs, dtype=np.float32)
    joints = np.asarray(out_joints, dtype=np.uint16)
    weights = np.asarray(out_weights, dtype=np.float32)
    triangles = np.asarray(faces, dtype=np.uint32)
    normals = vertex_normals(positions, triangles.astype(np.int64))

    blob = bytearray()
    views = []
    accessors = []

    def add_view(array: np.ndarray, target: int | None) -> int:
        raw = np.ascontiguousarray(array).tobytes()
        offset = len(blob)
        blob.extend(raw)
        blob.extend(b"\x00" * ((4 - (len(blob) % 4)) % 4))
        views.append(BufferView(buffer=0, byteOffset=offset, byteLength=len(raw), target=target))
        return len(views) - 1

    def add_accessor(array: np.ndarray, type_name: str, component: int, target: int | None) -> int:
        view = add_view(array, target)
        minimum = maximum = None
        if type_name != "MAT4":
            flat = array.reshape(array.shape[0], -1)
            minimum = flat.min(axis=0).astype(float).tolist()
            maximum = flat.max(axis=0).astype(float).tolist()
        accessors.append(
            Accessor(
                bufferView=view,
                componentType=component,
                count=array.shape[0],
                type=type_name,
                min=minimum,
                max=maximum,
            )
        )
        return len(accessors) - 1

    position_id = add_accessor(positions, "VEC3", FLOAT, ARRAY_BUFFER)
    normal_id = add_accessor(normals, "VEC3", FLOAT, ARRAY_BUFFER)
    uv_id = add_accessor(texcoords, "VEC2", FLOAT, ARRAY_BUFFER)
    joint_id = add_accessor(joints, "VEC4", UNSIGNED_SHORT, ARRAY_BUFFER)
    weight_id = add_accessor(weights, "VEC4", FLOAT, ARRAY_BUFFER)
    index_id = add_accessor(triangles.reshape(-1), "SCALAR", UNSIGNED_INT, ELEMENT_ARRAY_BUFFER)

    inverse = np.repeat(np.eye(4, dtype=np.float32)[None], len(world), axis=0)
    inverse[:, :3, 3] = -world.astype(np.float32)
    inverse_flat = np.ascontiguousarray(inverse.transpose(0, 2, 1)).reshape(len(world), 16)
    inverse_id = add_accessor(inverse_flat, "MAT4", FLOAT, None)

    def image_view(filename: str) -> int:
        raw = (SRC / filename).read_bytes()
        offset = len(blob)
        blob.extend(raw)
        blob.extend(b"\x00" * ((4 - (len(blob) % 4)) % 4))
        views.append(BufferView(buffer=0, byteOffset=offset, byteLength=len(raw)))
        return len(views) - 1

    albedo_view = image_view(f"{name}_albedo.png")
    normal_view = image_view(f"{name}_normal.png")

    children: dict[int, list[int]] = {index: [] for index in range(len(names))}
    for index, parent in enumerate(parents):
        if parent >= 0:
            children[int(parent)].append(index)
    local = world.copy()
    for index, parent in enumerate(parents):
        if parent >= 0:
            local[index] = world[index] - world[int(parent)]
    nodes = [
        Node(name=bone, translation=local[index].astype(float).tolist(), children=children[index] or None)
        for index, bone in enumerate(names)
    ]
    mesh_node = len(nodes)
    nodes.append(Node(name=name, mesh=0, skin=0))
    gltf = GLTF2(
        asset=Asset(version="2.0"),
        scene=0,
        scenes=[Scene(nodes=[mesh_node, 0])],
        nodes=nodes,
        skins=[Skin(name="SMPLX", joints=list(range(len(names))), inverseBindMatrices=inverse_id, skeleton=0)],
        meshes=[
            Mesh(
                primitives=[
                    Primitive(
                        attributes=Attributes(
                            POSITION=position_id,
                            NORMAL=normal_id,
                            TEXCOORD_0=uv_id,
                            JOINTS_0=joint_id,
                            WEIGHTS_0=weight_id,
                        ),
                        indices=index_id,
                        material=0,
                    )
                ]
            )
        ],
        materials=[
            Material(
                name=name,
                pbrMetallicRoughness=PbrMetallicRoughness(
                    baseColorTexture=TextureInfo(index=0),
                    metallicFactor=0,
                    roughnessFactor=0.72,
                ),
                normalTexture=NormalMaterialTexture(index=1),
                doubleSided=True,
            )
        ],
        images=[
            Image(mimeType="image/png", bufferView=albedo_view),
            Image(mimeType="image/png", bufferView=normal_view),
        ],
        textures=[Texture(sampler=0, source=0), Texture(sampler=0, source=1)],
        samplers=[Sampler()],
        buffers=[Buffer(byteLength=len(blob))],
        bufferViews=views,
        accessors=accessors,
    )
    gltf.set_binary_blob(bytes(blob))
    destination.parent.mkdir(parents=True, exist_ok=True)
    gltf.save(destination)
    print(f"{name}: {len(positions)} vertices -> {destination.name}")


def main() -> None:
    positions, joints, weights, names, parents, world = body_skin(BODY)
    for name, destination in OUT.items():
        pack(name, destination, names, parents, world, positions, joints, weights)


if __name__ == "__main__":
    main()
