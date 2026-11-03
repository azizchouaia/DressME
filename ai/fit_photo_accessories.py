"""Hat, shoes, and bag fitted like the shirt.

The shirt mesh sits on the body and carries a real albedo plus a normal map.
These three pieces do the same thing: the hat and the shoes are the head and
the feet pushed a little off the skin, and the bag uses the product photo.
Skin weights are copied from the nearest body vertex, which is how the shirt bends.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image
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
    Image as GltfImage,
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
from scipy import ndimage
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai"))

from skin_garments import BODY, _accessor, body_skin
from smplx_export import vertex_normals
from wear_accessories import cylinder_y, disc, ellipsoid, hemisphere

PHOTOS = Path(r"C:\Users\NADHIR\Desktop\clothes")
OUT = ROOT / "avatar_studio" / "web" / "garments"
TEX = OUT / "textured"


def body_faces() -> np.ndarray:
    gltf = GLTF2().load(str(BODY))
    blob = gltf.binary_blob()
    primitive = gltf.meshes[0].primitives[0]
    indices = _accessor(gltf, blob, primitive.indices).astype(np.int64).reshape(-1)
    return indices.reshape(-1, 3)


def cut_surface(positions, faces, mask):
    chosen = np.flatnonzero(mask)
    remap = np.full(len(positions), -1, dtype=np.int64)
    remap[chosen] = np.arange(len(chosen))
    kept = faces[mask[faces].all(axis=1)]
    local = remap[kept]
    vertices = positions[chosen].astype(np.float32)
    normals = vertex_normals(vertices, local)
    return vertices, local, normals, chosen


def boundary_loop(faces: np.ndarray) -> list[int]:
    counts: dict[tuple[int, int], int] = {}
    neighbours: dict[int, list[int]] = {}
    for a, b, c in faces:
        for u, v in ((int(a), int(b)), (int(b), int(c)), (int(c), int(a))):
            edge = (u, v) if u < v else (v, u)
            counts[edge] = counts.get(edge, 0) + 1
    for (u, v), count in counts.items():
        if count != 1:
            continue
        neighbours.setdefault(u, []).append(v)
        neighbours.setdefault(v, []).append(u)
    if not neighbours:
        return []
    start = next(iter(neighbours))
    loop = [start]
    previous = None
    current = start
    for _ in range(len(neighbours) + 2):
        nxt = [item for item in neighbours[current] if item != previous]
        if not nxt or nxt[0] == start:
            break
        previous, current = current, nxt[0]
        loop.append(current)
    return loop


def tile(patch: np.ndarray, size: int = 1024) -> np.ndarray:
    if patch.size == 0:
        return np.full((size, size, 3), 180, np.uint8)
    repeats_y = int(np.ceil(size / patch.shape[0]))
    repeats_x = int(np.ceil(size / patch.shape[1]))
    tiled = np.tile(patch, (repeats_y, repeats_x, 1))
    return tiled[:size, :size].astype(np.uint8)


def normal_from(albedo: np.ndarray) -> np.ndarray:
    gray = albedo.astype(np.float32).mean(axis=2)
    dx = ndimage.sobel(gray, axis=1)
    dy = ndimage.sobel(gray, axis=0)
    strength = 2.5
    normal = np.dstack([-dx * strength, -dy * strength, np.full_like(gray, 255.0)])
    normal /= np.maximum(np.linalg.norm(normal, axis=2, keepdims=True), 1e-6)
    return ((normal * 0.5 + 0.5) * 255).astype(np.uint8)


def straw_patch() -> np.ndarray:
    image = np.asarray(Image.open(PHOTOS / "hat.jpg").convert("RGB"))
    tan = (image[:, :, 0] > 150) & (image[:, :, 1] > 110) & (image[:, :, 2] < 190) & (image.min(axis=2) < 235)
    ys, xs = np.where(tan)
    if len(xs) < 100:
        return np.full((64, 64, 3), (194, 160, 107), np.uint8)
    crop = image[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    y0 = int(crop.shape[0] * 0.18)
    return crop[y0 : y0 + 72, crop.shape[1] // 2 - 36 : crop.shape[1] // 2 + 36]


def suede_patch() -> tuple[np.ndarray, np.ndarray]:
    image = np.asarray(Image.open(PHOTOS / "shoes.avif").convert("RGB"))
    blue = (image[:, :, 2] > image[:, :, 0] + 12) & (image[:, :, 2] > 45) & (image.max(axis=2) < 185)
    brown = (image[:, :, 0] > image[:, :, 2] + 30) & (image[:, :, 0] < 180) & (image[:, :, 1] > 40) & (image[:, :, 2] < 120)
    navy = image[blue]
    saddle = image[brown]
    navy_color = navy.mean(axis=0) if len(navy) else np.array([26, 41, 92])
    saddle_color = saddle.mean(axis=0) if len(saddle) else np.array([140, 92, 51])
    window = 48
    best = None
    step = 24
    for y in range(0, image.shape[0] - window, step):
        for x in range(0, image.shape[1] - window, step):
            score = blue[y : y + window, x : x + window].mean()
            if best is None or score > best[0]:
                best = (score, image[y : y + window, x : x + window])
    patch = best[1] if best and best[0] > 0.65 else np.full((window, window, 3), navy_color, np.uint8)
    return patch, saddle_color.astype(np.uint8)


def bag_crop() -> np.ndarray:
    image = np.asarray(Image.open(PHOTOS / "images.jpg").convert("RGB"))
    dark = image.mean(axis=2) < 78
    core = ndimage.binary_opening(dark, structure=np.ones((7, 7)))
    labels, count = ndimage.label(core)
    if count == 0:
        return np.full((256, 256, 3), 20, np.uint8)
    sizes = ndimage.sum(np.ones(labels.shape), labels, range(1, count + 1))
    main = int(np.argmax(sizes)) + 1
    ys, xs = np.where(labels == main)
    pad = 4
    crop = image[
        max(0, ys.min() - pad) : ys.max() + pad,
        max(0, xs.min() - pad) : xs.max() + pad,
    ].copy()
    crop = crop[: int(crop.shape[0] * 0.78)]
    white = crop.min(axis=2) > 210
    if (~white).any():
        crop[white] = crop[~white].mean(axis=0)
    return crop


def save_maps(name: str, albedo: np.ndarray) -> None:
    TEX.mkdir(parents=True, exist_ok=True)
    Image.fromarray(albedo).save(TEX / f"{name}_albedo.png")
    Image.fromarray(normal_from(albedo)).save(TEX / f"{name}_normal.png")


def pack(name, positions, uvs, faces, joints, weights, bone_names, parents, world) -> None:
    normals = vertex_normals(positions, faces.astype(np.int64))
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
        flat = array.reshape(array.shape[0], -1)
        accessors.append(
            Accessor(
                bufferView=view,
                componentType=component,
                count=array.shape[0],
                type=type_name,
                min=flat.min(axis=0).astype(float).tolist() if type_name != "MAT4" else None,
                max=flat.max(axis=0).astype(float).tolist() if type_name != "MAT4" else None,
            )
        )
        return len(accessors) - 1

    position_id = add_accessor(positions.astype(np.float32), "VEC3", FLOAT, ARRAY_BUFFER)
    normal_id = add_accessor(normals.astype(np.float32), "VEC3", FLOAT, ARRAY_BUFFER)
    uv_id = add_accessor(uvs.astype(np.float32), "VEC2", FLOAT, ARRAY_BUFFER)
    joint_id = add_accessor(joints.astype(np.uint16), "VEC4", UNSIGNED_SHORT, ARRAY_BUFFER)
    weight_id = add_accessor(weights.astype(np.float32), "VEC4", FLOAT, ARRAY_BUFFER)
    index_id = add_accessor(faces.astype(np.uint32).reshape(-1), "SCALAR", UNSIGNED_INT, ELEMENT_ARRAY_BUFFER)
    inverse = np.repeat(np.eye(4, dtype=np.float32)[None], len(world), axis=0)
    inverse[:, :3, 3] = -world.astype(np.float32)
    inverse_flat = np.ascontiguousarray(inverse.transpose(0, 2, 1)).reshape(len(world), 16)
    inverse_id = add_accessor(inverse_flat, "MAT4", FLOAT, None)

    def image_view(filename: str) -> int:
        raw = (TEX / filename).read_bytes()
        offset = len(blob)
        blob.extend(raw)
        blob.extend(b"\x00" * ((4 - (len(blob) % 4)) % 4))
        views.append(BufferView(buffer=0, byteOffset=offset, byteLength=len(raw)))
        return len(views) - 1

    children: dict[int, list[int]] = {index: [] for index in range(len(bone_names))}
    for index, parent in enumerate(parents):
        if parent >= 0:
            children[int(parent)].append(index)
    local = world.copy()
    for index, parent in enumerate(parents):
        if parent >= 0:
            local[index] = world[index] - world[int(parent)]
    nodes = [
        Node(name=bone, translation=local[index].astype(float).tolist(), children=children[index] or None)
        for index, bone in enumerate(bone_names)
    ]
    nodes.append(Node(name=name, mesh=0, skin=0))
    roughness = 0.42 if name == "bag" else 0.68
    gltf = GLTF2(
        asset=Asset(version="2.0"),
        scene=0,
        scenes=[Scene(nodes=[len(nodes) - 1, 0])],
        nodes=nodes,
        skins=[Skin(name="SMPLX", joints=list(range(len(bone_names))), inverseBindMatrices=inverse_id, skeleton=0)],
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
                    baseColorFactor=[1, 1, 1, 1],
                    metallicFactor=0.04 if name == "bag" else 0,
                    roughnessFactor=roughness,
                ),
                normalTexture=NormalMaterialTexture(index=1),
                doubleSided=True,
            )
        ],
        images=[
            GltfImage(mimeType="image/png", bufferView=image_view(f"{name}_albedo.png")),
            GltfImage(mimeType="image/png", bufferView=image_view(f"{name}_normal.png")),
        ],
        textures=[Texture(sampler=0, source=0), Texture(sampler=0, source=1)],
        samplers=[Sampler(wrapS=10497, wrapT=10497)],
        buffers=[Buffer(byteLength=len(blob))],
        bufferViews=views,
        accessors=accessors,
    )
    gltf.set_binary_blob(bytes(blob))
    gltf.save(str(OUT / f"{name}.glb"))


def bind_to_source(vertices, source_ids, body_joints, body_weights):
    joints = body_joints[source_ids]
    weights = body_weights[source_ids].astype(np.float32)
    weights /= np.maximum(weights.sum(axis=1, keepdims=True), 1e-8)
    return joints, weights


def bind_nearest(vertices, body_positions, body_joints, body_weights):
    _, nearest = cKDTree(body_positions).query(vertices, k=1)
    return bind_to_source(vertices, nearest, body_joints, body_weights)


def hat_mesh(positions, faces, world, names):
    head = world[names.index("head")]
    near = positions[np.linalg.norm(positions - head, axis=1) < 0.12]
    brow_y = float(head[1]) + 0.055
    brow = near[np.abs(near[:, 1] - brow_y) < 0.04]
    radial = np.sqrt((brow[:, 0] - head[0]) ** 2 + (brow[:, 2] - head[2]) ** 2)
    crown_r = float(np.clip(np.percentile(radial, 80) + 0.01, 0.09, 0.115))
    bottom = np.array([head[0], brow_y, head[2]], np.float32)
    parts = [
        cylinder_y(bottom, crown_r, 0.075),
        hemisphere(bottom + np.array([0, 0.075, 0]), (crown_r, 0.045, crown_r)),
        cylinder_y(bottom + np.array([0, 0.012, 0]), crown_r + 0.006, 0.016),
        disc(float(brow_y), (float(head[0]), float(head[2])), crown_r * 0.96, crown_r + 0.055),
    ]
    vertices, local = [], []
    offset = 0
    bands = []
    for index, (part_vertices, part_faces) in enumerate(parts):
        vertices.append(part_vertices)
        local.append(part_faces + offset)
        bands.append(np.full(len(part_vertices), index == 2))
        offset += len(part_vertices)
    vertices = np.vstack(vertices).astype(np.float32)
    faces_out = np.vstack(local)
    angle = np.arctan2(vertices[:, 2] - head[2], vertices[:, 0] - head[0])
    u = angle / (2 * np.pi) + 0.5
    height = (vertices[:, 1] - brow_y) / 0.12
    v = np.clip(0.62 + height * 0.34, 0.05, 0.98)
    band = np.concatenate(bands)
    v[band] = 0.50
    uvs = np.stack([u, v], axis=1).astype(np.float32)
    albedo = tile(straw_patch())
    albedo[470:560, :] = (18, 16, 15)
    source = np.full(len(vertices), names.index("head"), np.int64)
    # Every hat vertex is the head joint. bind_to_source expects body vertex ids,
    # so the caller handles this sentinel separately.
    return vertices, uvs, faces_out, source, albedo


def shoe_mesh(positions, world, names, side: str):
    foot = world[names.index(f"{side}_foot")]
    ankle = world[names.index(f"{side}_ankle")]
    other = world[names.index("right_foot" if side == "left" else "left_foot")]
    distance = np.linalg.norm(positions - foot, axis=1)
    other_distance = np.linalg.norm(positions - other, axis=1)
    cloud = positions[(distance < other_distance) & (positions[:, 1] <= ankle[1] + 0.02) & (distance < 0.16)]
    low = cloud.min(axis=0) - np.array([0.012, 0.004, 0.018])
    high = cloud.max(axis=0) + np.array([0.012, 0.02, 0.03])
    center = (low + high) / 2
    size = high - low
    upper_center = center + np.array([0, size[1] * 0.06, size[2] * 0.02])
    sole_center = np.array([center[0], low[1] + 0.007, center[2]])
    saddle_center = upper_center + np.array([0, size[1] * 0.28, size[2] * 0.08])
    parts = [
        ellipsoid(upper_center, (size[0] * 0.55, size[1] * 0.48, size[2] * 0.56), stacks=14, slices=22),
        ellipsoid(sole_center, (size[0] * 0.6, 0.012, size[2] * 0.6), stacks=8, slices=18),
        ellipsoid(saddle_center, (size[0] * 0.5, 0.01, size[2] * 0.22), stacks=6, slices=14),
    ]
    vertices, local = [], []
    kinds = []
    offset = 0
    for index, (part_vertices, part_faces) in enumerate(parts):
        vertices.append(part_vertices)
        local.append(part_faces + offset)
        kinds.append(np.full(len(part_vertices), index))
        offset += len(part_vertices)
    vertices = np.vstack(vertices).astype(np.float32)
    kind = np.concatenate(kinds)
    angle = np.arctan2(vertices[:, 2] - center[2], vertices[:, 0] - center[0])
    u = np.mod(angle / (2 * np.pi) + 0.5, 1)
    v = np.full(len(vertices), 0.55, np.float32)
    v[kind == 1] = 0.04
    v[kind == 2] = 0.78
    uvs = np.stack([u, v], axis=1).astype(np.float32)
    return vertices, uvs, np.vstack(local)


def bag_mesh(positions, world, names):
    hip = positions[(positions[:, 0] > 0.02) & (positions[:, 0] < 0.22) & (positions[:, 1] > 0.72) & (positions[:, 1] < 1.18)]
    front = float(np.percentile(hip[:, 2], 93))
    side = float(np.percentile(hip[:, 0], 62))
    height = float(np.percentile(hip[:, 1], 38))
    center = np.array([side, height - 0.02, front + 0.008 + 0.05], np.float32)
    size = np.array([0.24, 0.25, 0.10], np.float32)
    hx, hy, hz = size / 2
    corners = []
    uvs = []
    faces = []

    def quad(points, face_uvs):
        base = len(corners)
        corners.extend(points)
        uvs.extend(face_uvs)
        faces.append([base, base + 1, base + 2])
        faces.append([base, base + 2, base + 3])

    cx, cy, cz = center
    # Front shows the product photo. The other faces use the leather edge of that photo.
    quad(
        [[cx - hx, cy - hy, cz + hz], [cx + hx, cy - hy, cz + hz], [cx + hx, cy + hy, cz + hz], [cx - hx, cy + hy, cz + hz]],
        [[0.02, 0.02], [0.98, 0.02], [0.98, 0.98], [0.02, 0.98]],
    )
    quad(
        [[cx + hx, cy - hy, cz - hz], [cx - hx, cy - hy, cz - hz], [cx - hx, cy + hy, cz - hz], [cx + hx, cy + hy, cz - hz]],
        [[0.98, 0.02], [0.02, 0.02], [0.02, 0.98], [0.98, 0.98]],
    )
    quad(
        [[cx - hx, cy - hy, cz - hz], [cx - hx, cy - hy, cz + hz], [cx - hx, cy + hy, cz + hz], [cx - hx, cy + hy, cz - hz]],
        [[0.02, 0.02], [0.08, 0.02], [0.08, 0.98], [0.02, 0.98]],
    )
    quad(
        [[cx + hx, cy - hy, cz + hz], [cx + hx, cy - hy, cz - hz], [cx + hx, cy + hy, cz - hz], [cx + hx, cy + hy, cz + hz]],
        [[0.92, 0.02], [0.98, 0.02], [0.98, 0.98], [0.92, 0.98]],
    )
    quad(
        [[cx - hx, cy + hy, cz + hz], [cx + hx, cy + hy, cz + hz], [cx + hx, cy + hy, cz - hz], [cx - hx, cy + hy, cz - hz]],
        [[0.15, 0.92], [0.85, 0.92], [0.85, 0.98], [0.15, 0.98]],
    )
    quad(
        [[cx - hx, cy - hy, cz - hz], [cx + hx, cy - hy, cz - hz], [cx + hx, cy - hy, cz + hz], [cx - hx, cy - hy, cz + hz]],
        [[0.15, 0.02], [0.85, 0.02], [0.85, 0.08], [0.15, 0.08]],
    )
    shoulder = world[names.index("left_shoulder")]
    top = center + np.array([0, hy, 0], np.float32)

    def strap(end_z, sign):
        start = shoulder + np.array([0.01, -0.02, sign * 0.02], np.float32)
        end = top + np.array([-0.01, 0.0, end_z], np.float32)
        direction = end - start
        length = np.linalg.norm(direction)
        direction = direction / length
        helper = np.array([1.0, 0.0, 0.0])
        side_axis = np.cross(direction, helper)
        side_axis /= np.linalg.norm(side_axis)
        up = np.cross(side_axis, direction)
        rings = []
        for step in range(9):
            point = start + direction * (length * step / 8)
            ring = []
            for corner in range(6):
                angle = 2 * np.pi * corner / 6
                ring.append(point + 0.005 * (np.cos(angle) * side_axis + np.sin(angle) * up))
            rings.append(ring)
        for step in range(8):
            for corner in range(6):
                nxt = (corner + 1) % 6
                a = len(corners)
                corners.extend([rings[step][corner], rings[step][nxt], rings[step + 1][nxt], rings[step + 1][corner]])
                u0 = corner / 6
                u1 = (corner + 1) / 6
                v0 = step / 8
                v1 = (step + 1) / 8
                uvs.extend([[u0, v0], [u1, v0], [u1, v1], [u0, v1]])
                faces.append([a, a + 1, a + 2])
                faces.append([a, a + 2, a + 3])

    strap(0.05, 1)
    strap(-0.05, -1)
    vertices = np.asarray(corners, np.float32)
    return vertices, np.asarray(uvs, np.float32), np.asarray(faces, np.int64)


def main() -> None:
    positions, joints, weights, names, parents, world = body_skin(BODY)
    faces = body_faces()
    hat_vertices, hat_uvs, hat_faces, hat_source, hat_albedo = hat_mesh(positions, faces, world, names)
    save_maps("hat", hat_albedo)
    hat_joints = np.zeros((len(hat_vertices), 4), np.uint16)
    hat_joints[:, 0] = names.index("head")
    hat_weights = np.zeros((len(hat_vertices), 4), np.float32)
    hat_weights[:, 0] = 1
    pack("hat", hat_vertices, hat_uvs, hat_faces, hat_joints, hat_weights, names, parents, world)

    shoe_parts = [shoe_mesh(positions, world, names, side) for side in ("left", "right")]
    shoe_vertices = np.vstack([part[0] for part in shoe_parts])
    shoe_uvs = np.vstack([part[1] for part in shoe_parts])
    offset = 0
    shoe_faces = []
    for part in shoe_parts:
        shoe_faces.append(part[2] + offset)
        offset += len(part[0])
    shoe_faces = np.vstack(shoe_faces)
    suede, saddle = suede_patch()
    shoe_albedo = tile(suede)
    shoe_albedo[:90, :] = (12, 10, 9)
    shoe_albedo[740:900, :] = saddle
    save_maps("shoes", shoe_albedo)
    shoe_joints, shoe_weights = bind_nearest(shoe_vertices, positions, joints, weights)
    pack("shoes", shoe_vertices, shoe_uvs, shoe_faces, shoe_joints, shoe_weights, names, parents, world)

    bag_vertices, bag_uvs, bag_faces = bag_mesh(positions, world, names)
    crop = bag_crop()
    bag_albedo = np.asarray(Image.fromarray(crop).resize((1024, 1024), Image.Resampling.LANCZOS))
    save_maps("bag", bag_albedo)
    bag_joints, bag_weights = bind_nearest(bag_vertices, positions, joints, weights)
    pack("bag", bag_vertices, bag_uvs, bag_faces, bag_joints, bag_weights, names, parents, world)
    print(f"hat {len(hat_vertices)}  shoes {len(shoe_vertices)}  bag {len(bag_vertices)}  crop {crop.shape}")


if __name__ == "__main__":
    main()
