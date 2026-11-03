"""Hat, shoes, and a shoulder bag skinned to the same SMPL-X body.

Each piece is rigid: every vertex is fully weighted to one joint, so a pose
moves the hat with the head, the shoes with the feet, and the bag with the
shoulder.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ai"))

from skin_garments import body_skin
from smplx_export import pack_glb, vertex_normals

BODY = ROOT / "avatar_studio" / "web" / "smplx_thin.glb"
OUT = ROOT / "avatar_studio" / "web" / "garments"


def merge(parts: list[tuple[np.ndarray, np.ndarray]]) -> tuple[np.ndarray, np.ndarray]:
    vertices = []
    faces = []
    offset = 0
    for part_vertices, part_faces in parts:
        vertices.append(part_vertices)
        faces.append(part_faces + offset)
        offset += len(part_vertices)
    return np.vstack(vertices).astype(np.float32), np.vstack(faces).astype(np.int64)


def cylinder_y(bottom, radius: float, height: float, slices: int = 28) -> tuple[np.ndarray, np.ndarray]:
    cx, cy, cz = bottom
    ring = []
    for y in (cy, cy + height):
        for index in range(slices):
            angle = 2 * np.pi * index / slices
            ring.append([cx + radius * np.cos(angle), y, cz + radius * np.sin(angle)])
    bottom_index = len(ring)
    ring.append([cx, cy, cz])
    top_index = len(ring)
    ring.append([cx, cy + height, cz])
    faces = []
    for index in range(slices):
        nxt = (index + 1) % slices
        low = index
        high = slices + index
        low_next = nxt
        high_next = slices + nxt
        faces.append([low, high, low_next])
        faces.append([low_next, high, high_next])
        faces.append([bottom_index, low_next, low])
        faces.append([top_index, high, high_next])
    return np.asarray(ring, np.float32), np.asarray(faces, np.int64)


def hemisphere(center, radii, stacks: int = 8, slices: int = 28) -> tuple[np.ndarray, np.ndarray]:
    cx, cy, cz = center
    rx, ry, rz = radii
    vertices = []
    for stack in range(stacks + 1):
        theta = (np.pi / 2) * stack / stacks
        for index in range(slices):
            phi = 2 * np.pi * index / slices
            vertices.append(
                [
                    cx + rx * np.sin(theta) * np.cos(phi),
                    cy + ry * np.cos(theta),
                    cz + rz * np.sin(theta) * np.sin(phi),
                ]
            )
    faces = []
    for stack in range(stacks):
        for index in range(slices):
            nxt = (index + 1) % slices
            a = stack * slices + index
            b = stack * slices + nxt
            c = (stack + 1) * slices + index
            d = (stack + 1) * slices + nxt
            faces.append([a, c, b])
            faces.append([b, c, d])
    return np.asarray(vertices, np.float32), np.asarray(faces, np.int64)


def disc(center_y: float, origin_xz, inner: float, outer: float, slices: int = 32) -> tuple[np.ndarray, np.ndarray]:
    ox, oz = origin_xz
    vertices = []
    for radius in (inner, outer):
        for index in range(slices):
            angle = 2 * np.pi * index / slices
            vertices.append([ox + radius * np.cos(angle), center_y, oz + radius * np.sin(angle)])
    faces = []
    for index in range(slices):
        nxt = (index + 1) % slices
        a = index
        b = slices + index
        c = nxt
        d = slices + nxt
        faces.append([a, b, d])
        faces.append([a, d, c])
    return np.asarray(vertices, np.float32), np.asarray(faces, np.int64)


def box(center, size) -> tuple[np.ndarray, np.ndarray]:
    hx, hy, hz = (np.asarray(size, np.float64) / 2).tolist()
    cx, cy, cz = center
    vertices = []
    faces = []
    quads = [
        ([0, -1, 0], [1, 0, 0], [0, 0, 1]),
        ([0, 1, 0], [1, 0, 0], [0, 0, -1]),
        ([1, 0, 0], [0, 1, 0], [0, 0, -1]),
        ([-1, 0, 0], [0, 1, 0], [0, 0, 1]),
        ([0, 0, 1], [1, 0, 0], [0, 1, 0]),
        ([0, 0, -1], [-1, 0, 0], [0, 1, 0]),
    ]
    spans = {"x": hx, "y": hy, "z": hz}
    for normal, axis_u, axis_v in quads:
        normal = np.asarray(normal, np.float64)
        axis_u = np.asarray(axis_u, np.float64)
        axis_v = np.asarray(axis_v, np.float64)
        origin = np.array([cx, cy, cz]) + normal * np.array([hx, hy, hz])
        du = axis_u * np.array([hx, hy, hz])
        dv = axis_v * np.array([hx, hy, hz])
        base = len(vertices)
        for su in (-1, 1):
            for sv in (-1, 1):
                vertices.append(origin + su * du + sv * dv)
        faces.append([base, base + 1, base + 3])
        faces.append([base, base + 3, base + 2])
    return np.asarray(vertices, np.float32), np.asarray(faces, np.int64)


def tube(start, end, radius: float, sides: int = 8, segments: int = 8) -> tuple[np.ndarray, np.ndarray]:
    start = np.asarray(start, np.float64)
    end = np.asarray(end, np.float64)
    direction = end - start
    length = np.linalg.norm(direction)
    direction = direction / max(length, 1e-8)
    helper = np.array([0.0, 1.0, 0.0] if abs(direction[1]) < 0.85 else [1.0, 0.0, 0.0])
    side = np.cross(direction, helper)
    side /= np.linalg.norm(side)
    up = np.cross(side, direction)
    vertices = []
    for step in range(segments + 1):
        center = start + direction * (length * step / segments)
        for index in range(sides):
            angle = 2 * np.pi * index / sides
            vertices.append(center + radius * (np.cos(angle) * side + np.sin(angle) * up))
    faces = []
    for step in range(segments):
        for index in range(sides):
            nxt = (index + 1) % sides
            a = step * sides + index
            b = step * sides + nxt
            c = (step + 1) * sides + index
            d = (step + 1) * sides + nxt
            faces.append([a, c, b])
            faces.append([b, c, d])
    return np.asarray(vertices, np.float32), np.asarray(faces, np.int64)


def ellipsoid(center, radii, stacks: int = 12, slices: int = 20) -> tuple[np.ndarray, np.ndarray]:
    cx, cy, cz = center
    rx, ry, rz = radii
    vertices = []
    for stack in range(stacks + 1):
        theta = np.pi * stack / stacks
        for index in range(slices):
            phi = 2 * np.pi * index / slices
            vertices.append(
                [
                    cx + rx * np.sin(theta) * np.cos(phi),
                    cy + ry * np.cos(theta),
                    cz + rz * np.sin(theta) * np.sin(phi),
                ]
            )
    faces = []
    for stack in range(stacks):
        for index in range(slices):
            nxt = (index + 1) % slices
            a = stack * slices + index
            b = stack * slices + nxt
            c = (stack + 1) * slices + index
            d = (stack + 1) * slices + nxt
            faces.append([a, c, b])
            faces.append([b, c, d])
    return np.asarray(vertices, np.float32), np.asarray(faces, np.int64)


def paint(count: int, color) -> np.ndarray:
    return np.repeat(np.asarray(color, np.float32)[None], count, axis=0)


def save(vertices, faces, joint_ids, colors, names, parents, world, destination: Path) -> None:
    packed_joints = np.zeros((len(vertices), 4), np.uint16)
    packed_weights = np.zeros((len(vertices), 4), np.float32)
    packed_joints[:, 0] = joint_ids
    packed_weights[:, 0] = 1
    pack_glb(
        vertices,
        vertex_normals(vertices, faces),
        packed_joints,
        packed_weights,
        faces,
        names,
        parents,
        world,
        destination,
        colors=colors,
    )


def photo_colors() -> dict[str, np.ndarray]:
    """Straw, navy, and black taken from the local product photos."""
    straw = np.array([0.76, 0.63, 0.42], np.float32)
    band = np.array([0.08, 0.07, 0.06], np.float32)
    navy = np.array([0.10, 0.16, 0.36], np.float32)
    saddle = np.array([0.55, 0.36, 0.20], np.float32)
    sole = np.array([0.07, 0.06, 0.05], np.float32)
    leather = np.array([0.06, 0.06, 0.07], np.float32)
    folder = Path(r"C:\Users\NADHIR\Desktop\clothes")
    try:
        from PIL import Image

        hat = np.asarray(Image.open(folder / "hat.jpg").convert("RGB"), np.float32)
        kept = hat[hat.min(axis=2) < 240]
        dark = kept.mean(axis=1) < 90
        if (~dark).any():
            straw = kept[~dark].mean(axis=0) / 255
        if dark.any():
            band = kept[dark].mean(axis=0) / 255
        shoes = np.asarray(Image.open(folder / "shoes.avif").convert("RGB"), np.float32).reshape(-1, 3)
        blue = (shoes[:, 2] > shoes[:, 0] + 8) & (shoes[:, 2] > shoes[:, 1]) & (shoes[:, 2] > 50) & (shoes.max(axis=1) < 190)
        if blue.any():
            navy = shoes[blue].mean(axis=0) / 255
        brown = (shoes[:, 0] > shoes[:, 2] + 25) & (shoes[:, 0] > shoes[:, 1]) & (shoes[:, 0] < 190) & (shoes[:, 2] < 130)
        if brown.any():
            saddle = shoes[brown].mean(axis=0) / 255
    except Exception as error:
        print("photo colors", error)
    return {"straw": straw, "band": band, "navy": navy, "saddle": saddle, "sole": sole, "leather": leather}


def region(positions: np.ndarray, point: np.ndarray, radius: float) -> np.ndarray:
    return positions[np.linalg.norm(positions - point, axis=1) < radius]


def main() -> None:
    positions, _, _, names, parents, world = body_skin(BODY)
    index = {name: i for i, name in enumerate(names)}
    colors = photo_colors()
    head = world[index["head"]]
    head_pts = region(positions, head, 0.15)
    center = np.array([float(np.median(head_pts[:, 0])), float(head[1]), float(np.median(head_pts[:, 2]))])
    brow_y = float(head[1]) + 0.055
    brow = head_pts[np.abs(head_pts[:, 1] - brow_y) < 0.04]
    if len(brow) < 12:
        brow = head_pts
    radial = np.sqrt((brow[:, 0] - center[0]) ** 2 + (brow[:, 2] - center[2]) ** 2)
    crown_r = float(np.clip(np.percentile(radial, 85) + 0.008, 0.088, 0.112))
    brim_y = brow_y - 0.01
    crown_bottom = np.array([center[0], brim_y - 0.008, center[2]], np.float32)
    crown_h = max(0.085, float(head_pts[:, 1].max()) - brim_y + 0.012)
    hat_parts = [
        (*cylinder_y(crown_bottom, crown_r, crown_h * 0.72), colors["straw"]),
        (*hemisphere(crown_bottom + np.array([0, crown_h * 0.72, 0]), (crown_r, crown_h * 0.38, crown_r)), colors["straw"]),
        (*cylinder_y(crown_bottom + np.array([0, 0.012, 0]), crown_r + 0.004, 0.018), colors["band"]),
        (*disc(brim_y, (center[0], center[2]), crown_r * 0.92, crown_r + 0.048), colors["straw"]),
        (*disc(brim_y - 0.004, (center[0], center[2]), crown_r * 0.92, crown_r + 0.048), colors["straw"]),
    ]
    hat_vertices, hat_faces, hat_colors = merge_colored(hat_parts)

    def shoe(side: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        foot = world[index[f"{side}_foot"]]
        ankle = world[index[f"{side}_ankle"]]
        other = world[index["right_foot" if side == "left" else "left_foot"]]
        distance = np.linalg.norm(positions - foot, axis=1)
        other_distance = np.linalg.norm(positions - other, axis=1)
        cloud = positions[(distance < other_distance) & (positions[:, 1] <= ankle[1] + 0.015) & (distance < 0.16)]
        low = cloud.min(axis=0)
        high = cloud.max(axis=0)
        print(side, "foot verts", len(cloud), "y", round(float(low[1]), 3), round(float(high[1]), 3), "z", round(float(low[2]), 3), round(float(high[2]), 3))
        low = low - np.array([0.010, 0.006, 0.012])
        high = high + np.array([0.010, 0.014, 0.022])
        center_shoe = (low + high) / 2
        size = high - low
        upper_center = center_shoe + np.array([0, size[1] * 0.08, size[2] * 0.04])
        sole_center = np.array([center_shoe[0], low[1] + 0.006, center_shoe[2] + 0.004])
        saddle_center = upper_center + np.array([0, size[1] * 0.22, size[2] * 0.12])
        upper_v, upper_f = ellipsoid(upper_center, (size[0] * 0.52, size[1] * 0.42, size[2] * 0.52), stacks=12, slices=18)
        sole_v, sole_f = ellipsoid(sole_center, (size[0] * 0.56, 0.010, size[2] * 0.56), stacks=8, slices=16)
        saddle_v, saddle_f = box(saddle_center, (size[0] * 0.72, 0.008, size[2] * 0.28))
        return merge_colored(
            [
                (upper_v, upper_f, colors["navy"]),
                (sole_v, sole_f, colors["sole"]),
                (saddle_v, saddle_f, colors["saddle"]),
            ]
        )

    left_v, left_f, left_c = shoe("left")
    right_v, right_f, right_c = shoe("right")
    shoe_vertices, shoe_faces, shoe_colors = merge_colored([(left_v, left_f, left_c), (right_v, right_f, right_c)])
    shoe_joints = np.concatenate(
        [
            np.full(len(left_v), index["left_foot"], np.uint16),
            np.full(len(right_v), index["right_foot"], np.uint16),
        ]
    )

    hip = positions[(np.abs(positions[:, 0]) < 0.22) & (positions[:, 1] > 0.78) & (positions[:, 1] < 1.15)]
    left = hip[hip[:, 0] > 0.02]
    front = float(np.percentile(left[:, 2], 92))
    mid_y = float(np.percentile(left[:, 1], 40))
    side = float(np.percentile(left[:, 0], 70))
    # Held against the front of the hip. The photo's 15 cm depth stays, the width is narrowed so it stays on the body.
    bag_center = np.array([side, mid_y - 0.04, front + 0.055], np.float32)
    bag_body, bag_faces_only = box(bag_center, (0.20, 0.26, 0.11))
    shoulder = world[index["left_shoulder"]]
    top = bag_center + np.array([0.0, 0.14, 0.0])
    strap_a = tube(shoulder + np.array([0.0, -0.03, 0.03]), top + np.array([-0.02, 0.0, 0.06]), 0.006, segments=10)
    strap_b = tube(shoulder + np.array([0.015, -0.03, -0.01]), top + np.array([-0.02, 0.0, -0.06]), 0.006, segments=10)
    bag_vertices, bag_faces, bag_colors = merge_colored(
        [
            (bag_body, bag_faces_only, colors["leather"]),
            (*strap_a, colors["leather"]),
            (*strap_b, colors["leather"]),
        ]
    )

    OUT.mkdir(parents=True, exist_ok=True)
    save(hat_vertices, hat_faces, np.full(len(hat_vertices), index["head"], np.uint16), hat_colors, names, parents, world, OUT / "hat.glb")
    save(shoe_vertices, shoe_faces, shoe_joints, shoe_colors, names, parents, world, OUT / "shoes.glb")
    save(bag_vertices, bag_faces, np.full(len(bag_vertices), index["spine3"], np.uint16), bag_colors, names, parents, world, OUT / "bag.glb")
    print(
        f"hat crown {crown_r:.3f} at y {brim_y:.3f}  "
        f"shoes {len(shoe_vertices)}  bag x {bag_center[0]:.3f} y {bag_center[1]:.3f}"
    )


def merge_colored(parts: list[tuple[np.ndarray, np.ndarray, np.ndarray]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    vertices, faces, colors = [], [], []
    offset = 0
    for part_vertices, part_faces, part_colors in parts:
        vertices.append(part_vertices)
        faces.append(part_faces + offset)
        color = np.asarray(part_colors, np.float32)
        if color.ndim == 1:
            color = np.repeat(color[None], len(part_vertices), axis=0)
        colors.append(color)
        offset += len(part_vertices)
    return np.vstack(vertices).astype(np.float32), np.vstack(faces).astype(np.int64), np.vstack(colors).astype(np.float32)


if __name__ == "__main__":
    main()
