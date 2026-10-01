"""Procedurally generate the sample avatar and garment GLB files.

This script has no dependencies beyond the Python standard library so the
sample assets can be rebuilt on any machine without Blender installed.

All assets share one coordinate space (Y up, meters, feet at y=0, facing +Z),
which is what lets garments be layered onto the base avatar without any
runtime fitting. Real garments should be authored in Blender against
`base_avatar.glb` and exported with `export_garment.py`.

Usage:
    python blender/scripts/generate_sample_assets.py
"""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "frontend" / "public" / "models"

SEGMENTS = 40

Vec3 = tuple[float, float, float]


@dataclass
class Mesh:
    name: str
    color: tuple[float, float, float, float]
    roughness: float = 0.85
    double_sided: bool = False
    positions: list[Vec3] = field(default_factory=list)
    indices: list[int] = field(default_factory=list)

    def extend(self, positions: list[Vec3], indices: list[int]) -> None:
        offset = len(self.positions)
        self.positions.extend(positions)
        self.indices.extend(i + offset for i in indices)


# --------------------------------------------------------------------------
# Geometry primitives
# --------------------------------------------------------------------------


def lathe(
    profile: list[tuple[float, float]],
    *,
    scale_x: float = 1.0,
    scale_z: float = 1.0,
    offset_z: float = 0.0,
    segments: int = SEGMENTS,
) -> tuple[list[Vec3], list[int]]:
    """Revolve a (radius, y) profile around the Y axis with an elliptical section.

    Profile points with radius 0 collapse into a single pole vertex so closed
    shapes stay watertight.
    """
    positions: list[Vec3] = []
    rings: list[list[int]] = []
    for radius, y in profile:
        if radius <= 1e-6:
            positions.append((0.0, y, offset_z))
            rings.append([len(positions) - 1] * segments)
            continue
        ring = []
        for s in range(segments):
            theta = 2 * math.pi * s / segments
            positions.append(
                (
                    math.cos(theta) * radius * scale_x,
                    y,
                    math.sin(theta) * radius * scale_z + offset_z,
                )
            )
            ring.append(len(positions) - 1)
        rings.append(ring)

    # Winding depends on whether the profile goes up or down.
    ascending = profile[-1][1] >= profile[0][1]
    indices: list[int] = []
    for r in range(len(rings) - 1):
        a_ring, b_ring = rings[r], rings[r + 1]
        for s in range(segments):
            n = (s + 1) % segments
            a, b, c, d = a_ring[s], a_ring[n], b_ring[s], b_ring[n]
            tris = [(a, c, b), (b, c, d)] if ascending else [(a, b, c), (b, d, c)]
            for tri in tris:
                if len({tri[0], tri[1], tri[2]}) == 3:
                    indices.extend(tri)
    return positions, indices


def transform(
    positions: list[Vec3], *, rotate_z: float = 0.0, translate: Vec3 = (0, 0, 0)
) -> list[Vec3]:
    c, s = math.cos(rotate_z), math.sin(rotate_z)
    tx, ty, tz = translate
    return [(x * c - y * s + tx, x * s + y * c + ty, z + tz) for x, y, z in positions]


def mirror_x(positions: list[Vec3], indices: list[int]) -> tuple[list[Vec3], list[int]]:
    mirrored = [(-x, y, z) for x, y, z in positions]
    flipped: list[int] = []
    for i in range(0, len(indices), 3):
        flipped.extend([indices[i], indices[i + 2], indices[i + 1]])
    return mirrored, flipped


def compute_normals(positions: list[Vec3], indices: list[int]) -> list[Vec3]:
    acc = [[0.0, 0.0, 0.0] for _ in positions]
    for i in range(0, len(indices), 3):
        a, b, c = indices[i], indices[i + 1], indices[i + 2]
        pa, pb, pc = positions[a], positions[b], positions[c]
        u = [pb[k] - pa[k] for k in range(3)]
        v = [pc[k] - pa[k] for k in range(3)]
        n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
        for idx in (a, b, c):
            for k in range(3):
                acc[idx][k] += n[k]
    normals: list[Vec3] = []
    for n in acc:
        length = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
        normals.append((n[0] / length, n[1] / length, n[2] / length))
    return normals


# --------------------------------------------------------------------------
# Body proportions (shared by avatar and garments)
# --------------------------------------------------------------------------

LEG_X = 0.095
SHOULDER_JOINT = (0.185, 1.415, 0.0)
ARM_ANGLE = math.radians(14)
TORSO_DEPTH = 0.62

TORSO_PROFILE = [
    (0.0, 0.84),
    (0.12, 0.845),
    (0.168, 0.88),
    (0.178, 0.95),
    (0.160, 1.03),
    (0.150, 1.08),
    (0.160, 1.20),
    (0.178, 1.32),
    (0.180, 1.38),
    (0.160, 1.44),
    (0.090, 1.475),
    (0.0, 1.48),
]

LEG_PROFILE = [
    (0.0, 0.07),
    (0.038, 0.075),
    (0.040, 0.12),
    (0.055, 0.32),
    (0.047, 0.50),
    (0.062, 0.62),
    (0.080, 0.80),
    (0.088, 0.90),
    (0.0, 0.93),
]

ARM_PROFILE = [  # distance down the arm, measured from the shoulder joint
    (0.0, 0.03),
    (0.056, 0.0),
    (0.052, -0.06),
    (0.042, -0.27),
    (0.037, -0.32),
    (0.033, -0.50),
    (0.028, -0.55),
    (0.034, -0.60),
    (0.030, -0.68),
    (0.0, -0.71),
]


def offset_profile(
    profile: list[tuple[float, float]], amount: float, y_min: float, y_max: float
) -> list[tuple[float, float]]:
    """Inflate a body profile and clip it to [y_min, y_max] for a garment shell."""
    out: list[tuple[float, float]] = []
    lo, hi = min(y_min, y_max), max(y_min, y_max)
    for i, (r, y) in enumerate(profile):
        if r <= 1e-6:
            continue
        if lo <= y <= hi:
            out.append((r + amount, y))
    # Interpolate exact boundary rings so garment hems sit where requested.
    def sample(at: float) -> float:
        pts = [(r, y) for r, y in profile]
        for (r0, y0), (r1, y1) in zip(pts, pts[1:]):
            if min(y0, y1) <= at <= max(y0, y1) and y0 != y1:
                t = (at - y0) / (y1 - y0)
                return r0 + (r1 - r0) * t + amount
        return amount

    ys = {round(y, 5) for _, y in out}
    if round(y_min, 5) not in ys:
        out.append((sample(y_min), y_min))
    if round(y_max, 5) not in ys:
        out.append((sample(y_max), y_max))
    descending = profile[-1][1] < profile[0][1]
    out.sort(key=lambda p: p[1], reverse=descending)
    return out


def add_arm_pair(mesh: Mesh, profile: list[tuple[float, float]], scale: float = 1.0) -> None:
    positions, indices = lathe(profile, scale_x=scale, scale_z=scale)
    right = transform(positions, rotate_z=ARM_ANGLE, translate=SHOULDER_JOINT)
    mesh.extend(right, indices)
    left, left_idx = mirror_x(right, indices)
    mesh.extend(left, left_idx)


def add_leg_pair(mesh: Mesh, profile: list[tuple[float, float]]) -> None:
    positions, indices = lathe(profile, scale_z=0.95)
    right = transform(positions, translate=(LEG_X, 0, 0))
    mesh.extend(right, indices)
    left, left_idx = mirror_x(right, indices)
    mesh.extend(left, left_idx)


def add_feet(mesh: Mesh, inflate: float = 0.0, y_max: float = 0.085) -> None:
    profile = [
        (0.0, 0.0),
        (0.045 + inflate, 0.002),
        (0.050 + inflate, 0.03),
        (0.046 + inflate, 0.06),
        (0.030 + inflate, y_max),
        (0.0, y_max + 0.005),
    ]
    positions, indices = lathe(profile, scale_x=1.0, scale_z=2.3, offset_z=0.045)
    right = transform(positions, translate=(LEG_X, 0, 0))
    mesh.extend(right, indices)
    left, left_idx = mirror_x(right, indices)
    mesh.extend(left, left_idx)


# --------------------------------------------------------------------------
# Assets
# --------------------------------------------------------------------------


def rgba(hex_color: str) -> tuple[float, float, float, float]:
    """Convert sRGB hex to linear RGBA as required by glTF baseColorFactor."""
    hex_color = hex_color.lstrip("#")
    srgb = [int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
    return (linear[0], linear[1], linear[2], 1.0)


def build_avatar() -> list[Mesh]:
    skin = Mesh("Body", rgba("#d9cfc4"), roughness=0.6)
    skin.extend(*lathe(TORSO_PROFILE, scale_z=TORSO_DEPTH))
    add_leg_pair(skin, LEG_PROFILE)
    add_arm_pair(skin, ARM_PROFILE)
    neck = [(0.0, 1.43), (0.052, 1.44), (0.048, 1.52), (0.050, 1.57), (0.0, 1.58)]
    skin.extend(*lathe(neck, scale_z=0.95))
    head = [
        (0.0, 1.535),
        (0.045, 1.545),
        (0.080, 1.58),
        (0.092, 1.64),
        (0.094, 1.68),
        (0.088, 1.73),
        (0.065, 1.77),
        (0.0, 1.79),
    ]
    skin.extend(*lathe(head, scale_x=0.86, scale_z=1.0, offset_z=0.01))
    add_feet(skin)
    return [skin]


def build_tshirt(color: str) -> list[Mesh]:
    mesh = Mesh("TShirt", rgba(color), double_sided=True)
    body = offset_profile(TORSO_PROFILE, 0.026, 0.93, 1.455)
    body.append((0.085, 1.478))
    mesh.extend(*lathe(body, scale_z=TORSO_DEPTH * 1.04))
    sleeve = offset_profile(ARM_PROFILE, 0.02, -0.20, 0.0)
    sleeve.insert(0, (0.0, 0.052))
    add_arm_pair(mesh, sleeve)
    return [mesh]


def build_longsleeve(color: str) -> list[Mesh]:
    mesh = Mesh("Shirt", rgba(color), double_sided=True)
    body = offset_profile(TORSO_PROFILE, 0.028, 0.90, 1.455)
    body.append((0.082, 1.48))
    mesh.extend(*lathe(body, scale_z=TORSO_DEPTH * 1.04))
    sleeve = offset_profile(ARM_PROFILE, 0.018, -0.53, 0.0)
    sleeve.insert(0, (0.0, 0.054))
    add_arm_pair(mesh, sleeve)
    return [mesh]


def build_jacket(color: str, trim: str) -> list[Mesh]:
    shell = Mesh("Jacket", rgba(color), roughness=0.55, double_sided=True)
    body = offset_profile(TORSO_PROFILE, 0.046, 0.86, 1.455)
    body.append((0.095, 1.50))
    shell.extend(*lathe(body, scale_z=TORSO_DEPTH * 1.08))
    sleeve = offset_profile(ARM_PROFILE, 0.04, -0.535, 0.0)
    sleeve.insert(0, (0.0, 0.068))
    add_arm_pair(shell, sleeve)
    collar = [(0.09, 1.45), (0.1, 1.47), (0.094, 1.54)]
    shell.extend(*lathe(collar, scale_z=1.0))

    hem = Mesh("Hem", rgba(trim), roughness=0.5, double_sided=True)
    hem.extend(*lathe(offset_profile(TORSO_PROFILE, 0.05, 0.86, 0.895), scale_z=TORSO_DEPTH * 1.1))
    cuff = offset_profile(ARM_PROFILE, 0.044, -0.535, -0.50)
    add_arm_pair(hem, cuff)
    return [shell, hem]


def build_pants(color: str, hem_y: float, name: str) -> list[Mesh]:
    mesh = Mesh(name, rgba(color), double_sided=True)
    hips = offset_profile(TORSO_PROFILE, 0.012, 0.845, 1.07)
    hips.insert(0, (0.0, 0.84))
    mesh.extend(*lathe(hips, scale_z=TORSO_DEPTH * 1.04))
    leg = offset_profile(LEG_PROFILE, 0.016, hem_y, 0.905)
    leg.append((0.0, 0.93))
    add_leg_pair(mesh, leg)

    belt = Mesh("Waistband", rgba(color), roughness=0.7, double_sided=True)
    band = offset_profile(TORSO_PROFILE, 0.015, 1.035, 1.07)
    belt.extend(*lathe(band, scale_z=TORSO_DEPTH * 1.05))
    return [mesh, belt]


def build_sneakers(upper: str, sole: str) -> list[Mesh]:
    upper_mesh = Mesh("Upper", rgba(upper), roughness=0.7)
    add_feet(upper_mesh, inflate=0.012, y_max=0.10)
    sole_mesh = Mesh("Sole", rgba(sole), roughness=0.9)
    profile = [(0.0, 0.0), (0.06, 0.0), (0.062, 0.022), (0.0, 0.022)]
    positions, indices = lathe(profile, scale_z=2.2, offset_z=0.045)
    right = transform(positions, translate=(LEG_X, -0.004, 0))
    sole_mesh.extend(right, indices)
    sole_mesh.extend(*mirror_x(right, indices))
    return [upper_mesh, sole_mesh]


# --------------------------------------------------------------------------
# GLB writer
# --------------------------------------------------------------------------


def write_glb(path: Path, meshes: list[Mesh], asset_name: str) -> None:
    binary = bytearray()
    buffer_views: list[dict] = []
    accessors: list[dict] = []
    gltf_meshes: list[dict] = []
    materials: list[dict] = []
    nodes: list[dict] = []

    def add_view(data: bytes, target: int) -> int:
        while len(binary) % 4:
            binary.append(0)
        buffer_views.append(
            {"buffer": 0, "byteOffset": len(binary), "byteLength": len(data), "target": target}
        )
        binary.extend(data)
        return len(buffer_views) - 1

    for mesh in meshes:
        normals = compute_normals(mesh.positions, mesh.indices)
        pos_bytes = b"".join(struct.pack("<3f", *p) for p in mesh.positions)
        nrm_bytes = b"".join(struct.pack("<3f", *n) for n in normals)
        use_u32 = len(mesh.positions) > 65535
        idx_bytes = struct.pack(f"<{len(mesh.indices)}{'I' if use_u32 else 'H'}", *mesh.indices)

        mins = [min(p[i] for p in mesh.positions) for i in range(3)]
        maxs = [max(p[i] for p in mesh.positions) for i in range(3)]
        accessors.append(
            {
                "bufferView": add_view(pos_bytes, 34962),
                "componentType": 5126,
                "count": len(mesh.positions),
                "type": "VEC3",
                "min": mins,
                "max": maxs,
            }
        )
        pos_acc = len(accessors) - 1
        accessors.append(
            {
                "bufferView": add_view(nrm_bytes, 34962),
                "componentType": 5126,
                "count": len(normals),
                "type": "VEC3",
            }
        )
        nrm_acc = len(accessors) - 1
        accessors.append(
            {
                "bufferView": add_view(idx_bytes, 34963),
                "componentType": 5125 if use_u32 else 5123,
                "count": len(mesh.indices),
                "type": "SCALAR",
            }
        )
        idx_acc = len(accessors) - 1

        materials.append(
            {
                "name": f"{mesh.name}_Material",
                "pbrMetallicRoughness": {
                    "baseColorFactor": list(mesh.color),
                    "metallicFactor": 0.0,
                    "roughnessFactor": mesh.roughness,
                },
                "doubleSided": mesh.double_sided,
            }
        )
        gltf_meshes.append(
            {
                "name": mesh.name,
                "primitives": [
                    {
                        "attributes": {"POSITION": pos_acc, "NORMAL": nrm_acc},
                        "indices": idx_acc,
                        "material": len(materials) - 1,
                    }
                ],
            }
        )
        nodes.append({"name": mesh.name, "mesh": len(gltf_meshes) - 1})

    while len(binary) % 4:
        binary.append(0)

    gltf = {
        "asset": {"version": "2.0", "generator": "smart-wardrobe/generate_sample_assets.py"},
        "scene": 0,
        "scenes": [{"name": asset_name, "nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": gltf_meshes,
        "materials": materials,
        "accessors": accessors,
        "bufferViews": buffer_views,
        "buffers": [{"byteLength": len(binary)}],
    }
    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    json_bytes += b" " * ((4 - len(json_bytes) % 4) % 4)

    total = 12 + 8 + len(json_bytes) + 8 + len(binary)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(json_bytes), 0x4E4F534A))
        f.write(json_bytes)
        f.write(struct.pack("<II", len(binary), 0x004E4942))
        f.write(binary)


ASSETS: dict[str, list[Mesh]] = {
    "avatar/base_avatar.glb": build_avatar(),
    "garments/black_tshirt.glb": build_tshirt("#1d1d1f"),
    "garments/white_tshirt.glb": build_tshirt("#f2f0eb"),
    "garments/olive_longsleeve.glb": build_longsleeve("#6b6a45"),
    "garments/blue_jeans.glb": build_pants("#3d5a80", 0.075, "Jeans"),
    "garments/black_jeans.glb": build_pants("#26272b", 0.075, "Jeans"),
    "garments/sand_shorts.glb": build_pants("#c8b593", 0.56, "Shorts"),
    "garments/black_jacket.glb": build_jacket("#18181a", "#9a9a9e"),
    "garments/white_sneakers.glb": build_sneakers("#f5f5f2", "#d4d0c8"),
    "garments/black_sneakers.glb": build_sneakers("#222224", "#f0eee8"),
}


def main() -> None:
    for relative, meshes in ASSETS.items():
        target = OUTPUT_DIR / relative
        write_glb(target, meshes, Path(relative).stem)
        size_kb = target.stat().st_size / 1024
        print(f"wrote {target.relative_to(REPO_ROOT)} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    main()
