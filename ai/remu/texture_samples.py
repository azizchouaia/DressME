"""Lay internet clothing samples onto the skin-fitted garments.

The shirt, pants, sneakers, and cap keep the joints they already have.
A chest print from a free shirt photo is mapped once onto the front of the
shirt. The pants use a plain denim weave from a jeans photo, with no logo.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter
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
    PbrMetallicRoughness,
    Primitive,
    Sampler,
    Scene,
    Skin,
    Texture,
    TextureInfo,
)

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))
sys.path.insert(0, str(ROOT / "ai" / "remu"))

from garment_job import _export_faces  # noqa: E402
from skin_garments import body_skin  # noqa: E402
from smplx_export import vertex_normals  # noqa: E402

WEB = ROOT / "avatar_studio" / "web" / "garments"
SAMPLES = WEB / "saved" / "samples"
BACKUP = WEB / "saved" / "flat_fit"


def _read_mesh(path: Path):
    positions, joints, weights, names, parents, world = body_skin(path)
    gltf = GLTF2().load(str(path))
    blob = gltf.binary_blob()
    primitive = gltf.meshes[0].primitives[0]
    faces = _export_faces(gltf, blob, primitive.indices)
    normals = vertex_normals(positions, faces)
    return positions, normals, faces, joints, weights, names, parents, world


def _graphic() -> Image.Image:
    """Keep the dark chest print and drop the wall, neck, and collar around it."""
    image = Image.open(SAMPLES / "tee-curly.jpg").convert("RGB")
    array = np.asarray(image)
    height, width, _ = array.shape
    region = array[int(height * 0.60):int(height * 0.88), int(width * 0.34):int(width * 0.66)]
    gray = region.mean(axis=2)
    ink = gray < 78
    ink[:, : int(region.shape[1] * 0.12)] = False
    ink[: int(region.shape[0] * 0.08), :] = False
    ys, xs = np.nonzero(ink)
    if len(xs) < 40:
        raise RuntimeError("The shirt photo has no dark print to place on the chest.")
    pad = 12
    x0 = max(0, int(xs.min()) - pad)
    y0 = max(0, int(ys.min()) - pad)
    x1 = min(region.shape[1], int(xs.max()) + pad)
    y1 = min(region.shape[0], int(ys.max()) + pad)
    crop = region[y0:y1, x0:x1]
    crop_gray = crop.mean(axis=2)
    keep = crop_gray < 90
    cotton = np.array([214, 211, 206], dtype=np.uint8)
    isolated = np.broadcast_to(cotton, crop.shape).copy()
    isolated[keep] = crop[keep]
    graphic = Image.fromarray(isolated)
    graphic.save(SAMPLES / "graphic.png")
    return graphic


def _denim() -> Image.Image:
    image = Image.open(SAMPLES / "jeans.jpg").convert("RGB")
    array = np.asarray(image)
    height, width, _ = array.shape
    patch = array[int(height * 0.62):int(height * 0.82), int(width * 0.08):int(width * 0.28)]
    cloth = Image.fromarray(patch).resize((256, 256), Image.Resampling.LANCZOS)
    cloth = cloth.filter(ImageFilter.SMOOTH)
    cloth.save(SAMPLES / "denim.png")
    return cloth


def _cotton(color: tuple[int, int, int], size: int = 1024) -> np.ndarray:
    noise = np.random.default_rng(7).normal(0, 7, (size, size, 1))
    base = np.array(color, dtype=np.float32).reshape(1, 1, 3)
    return np.clip(base + noise, 0, 255).astype(np.uint8)


def _shirt_albedo(graphic: Image.Image) -> Image.Image:
    size = 1024
    albedo = _cotton((214, 211, 206), size)
    front = albedo[:, : size // 2]
    placed = graphic.resize((300, 360), Image.Resampling.LANCZOS)
    canvas = Image.fromarray(front)
    canvas.paste(placed, ((front.shape[1] - placed.width) // 2, 170))
    albedo[:, : size // 2] = np.asarray(canvas)
    image = Image.fromarray(albedo)
    image.save(SAMPLES / "shirt_albedo.png")
    return image


def _pants_albedo(denim: Image.Image) -> Image.Image:
    """Use the jeans photo for the blue, as a weave instead of a repeated picture."""
    sample = np.asarray(denim).reshape(-1, 3).astype(np.float32)
    blue = sample[(sample[:, 2] > sample[:, 0]) & (sample.mean(axis=1) > 25) & (sample.mean(axis=1) < 150)]
    color = np.median(blue, axis=0) if len(blue) else np.array([58, 78, 108], dtype=np.float32)
    size = 1024
    rng = np.random.default_rng(3)
    weave = np.sin(np.arange(size) * 1.3).astype(np.float32)[:, None] * 5
    grain = rng.normal(0, 6, (size, size, 1)).astype(np.float32)
    albedo = np.clip(color.reshape(1, 1, 3) + weave[:, :, None] + grain, 0, 255).astype(np.uint8)
    image = Image.fromarray(albedo)
    image.save(SAMPLES / "pants_albedo.png")
    return image


def _solid_albedo(color: tuple[int, int, int], name: str) -> Image.Image:
    image = Image.fromarray(_cotton(color, 512))
    image.save(SAMPLES / name)
    return image


def _uvs(positions: np.ndarray, normals: np.ndarray, tile: float) -> np.ndarray:
    uvs = np.zeros((len(positions), 2), dtype=np.float32)
    if tile:
        uvs[:, 0] = positions[:, 0] * tile
        uvs[:, 1] = positions[:, 1] * tile
        return uvs
    span_x = max(float(positions[:, 0].max() - positions[:, 0].min()), 1e-6)
    span_y = max(float(positions[:, 1].max() - positions[:, 1].min()), 1e-6)
    across = (positions[:, 0] - float(positions[:, 0].min())) / span_x
    down = 1.0 - (positions[:, 1] - float(positions[:, 1].min())) / span_y
    front = normals[:, 2] >= 0
    uvs[front, 0] = across[front] * 0.5
    uvs[front, 1] = down[front]
    uvs[~front, 0] = 0.5 + across[~front] * 0.5
    uvs[~front, 1] = down[~front]
    return uvs


def _pack(path: Path, albedo: Image.Image, tile: float, uvs: np.ndarray | None = None, normals: np.ndarray | None = None, roughness: float = 0.74) -> None:
    positions, face_normals, faces, joints, weights, names, parents, world = _read_mesh(path)
    if normals is None:
        normals = face_normals
    if uvs is None:
        uvs = _uvs(positions, normals, tile)
    blob = bytearray()
    views = []
    accessors = []

    def add_view(array: np.ndarray, target: int | None) -> int:
        raw = np.ascontiguousarray(array).tobytes()
        offset = len(blob)
        blob.extend(raw)
        views.append(BufferView(buffer=0, byteOffset=offset, byteLength=len(raw), target=target))
        return len(views) - 1

    def add_accessor(array: np.ndarray, type_name: str, component: int, target: int | None) -> int:
        view = add_view(array, target)
        count = int(array.size) if type_name == "SCALAR" else len(array)
        minimum = maximum = None
        if array.ndim == 2 and array.shape[1] == 3 and array.dtype == np.float32:
            minimum = array.min(axis=0).astype(float).tolist()
            maximum = array.max(axis=0).astype(float).tolist()
        accessors.append(
            Accessor(
                bufferView=view,
                componentType=component,
                count=count,
                type=type_name,
                min=minimum,
                max=maximum,
            )
        )
        return len(accessors) - 1

    position_id = add_accessor(positions.astype(np.float32), "VEC3", FLOAT, ARRAY_BUFFER)
    normal_id = add_accessor(normals.astype(np.float32), "VEC3", FLOAT, ARRAY_BUFFER)
    uv_id = add_accessor(uvs.astype(np.float32), "VEC2", FLOAT, ARRAY_BUFFER)
    joint_id = add_accessor(joints.astype(np.uint16), "VEC4", UNSIGNED_SHORT, ARRAY_BUFFER)
    weight_id = add_accessor(weights.astype(np.float32), "VEC4", FLOAT, ARRAY_BUFFER)
    index_id = add_accessor(faces.astype(np.uint32), "SCALAR", UNSIGNED_INT, ELEMENT_ARRAY_BUFFER)

    png = SAMPLES / "_albedo_pack.png"
    albedo.save(png)
    raw = png.read_bytes()
    offset = len(blob)
    blob.extend(raw)
    blob.extend(b"\x00" * ((4 - (len(blob) % 4)) % 4))
    views.append(BufferView(buffer=0, byteOffset=offset, byteLength=len(raw)))
    image_view = len(views) - 1

    inverse = np.repeat(np.eye(4, dtype=np.float32)[None], len(world), axis=0)
    inverse[:, :3, 3] = -world.astype(np.float32)
    inverse_flat = np.ascontiguousarray(inverse.transpose(0, 2, 1)).reshape(len(world), 16)
    inverse_id = add_accessor(inverse_flat, "MAT4", FLOAT, None)

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
    nodes.append(Node(name=path.stem, mesh=0, skin=0))
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
                name=path.stem,
                pbrMetallicRoughness=PbrMetallicRoughness(
                    baseColorTexture=TextureInfo(index=0),
                    metallicFactor=0,
                    roughnessFactor=roughness,
                ),
                doubleSided=True,
            )
        ],
        images=[GltfImage(mimeType="image/png", bufferView=image_view)],
        textures=[Texture(sampler=0, source=0)],
        samplers=[Sampler()],
        buffers=[Buffer(byteLength=len(blob))],
        bufferViews=views,
        accessors=accessors,
    )
    gltf.set_binary_blob(bytes(blob))
    gltf.save(path)


def main() -> None:
    BACKUP.mkdir(parents=True, exist_ok=True)
    for name in ("fitted.glb", "pants.glb", "sneakers.glb", "cap.glb"):
        source = WEB / name
        target = BACKUP / name
        if source.is_file() and not target.is_file():
            shutil.copy2(source, target)
    graphic = _graphic()
    denim = _denim()
    _pack(WEB / "fitted.glb", _shirt_albedo(graphic), 0)
    _pack(WEB / "pants.glb", _pants_albedo(denim), 0)
    _pack(WEB / "sneakers.glb", _solid_albedo((32, 32, 34), "shoe_albedo.png"), 0)
    _pack(WEB / "cap.glb", _solid_albedo((48, 48, 52), "cap_albedo.png"), 0)
    print("textured fitted.glb pants.glb sneakers.glb cap.glb")


if __name__ == "__main__":
    main()
