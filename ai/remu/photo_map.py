"""Map a front photo onto a skin-fitted shirt and pants, outdoors-style."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))
sys.path.insert(0, str(ROOT / "ai" / "remu"))

from vision_fit import PANTS, SKIRT, UPPER, _person, _segment, _span


def _shirt_color(image: np.ndarray, labels: np.ndarray) -> list[int]:
    upper = labels == UPPER
    pixels = image[upper]
    if len(pixels) < 80:
        return [210, 230, 70]
    sat = pixels.max(axis=1) - pixels.min(axis=1)
    bright = pixels[(sat > 40) & (pixels[:, 1] > pixels[:, 2])]
    sample = bright if len(bright) > 80 else pixels
    return [int(v) for v in np.median(sample, axis=0)]


def _pants_color(image: np.ndarray, labels: np.ndarray) -> list[int]:
    lower = np.isin(labels, (PANTS, SKIRT))
    ys, xs = np.nonzero(lower)
    if len(ys) < 80:
        return [186, 170, 138]
    y0, y1 = np.percentile(ys, [22, 78])
    band = lower.copy()
    band[: int(y0)] = False
    band[int(y1):] = False
    pixels = image[band].astype(np.float32)
    if len(pixels) < 40:
        pixels = image[lower].astype(np.float32)
    beige = pixels[
        (pixels[:, 0] > 125)
        & (pixels[:, 1] > 115)
        & (pixels[:, 2] < pixels[:, 0] + 12)
        & (pixels.mean(axis=1) < 210)
    ]
    sample = beige if len(beige) > 40 else pixels
    color = np.median(sample, axis=0)
    if color[0] < 155 or color[2] + 6 > color[0] or color[1] < color[0] - 28:
        color = np.array([201, 184, 132], dtype=np.float32)
    else:
        color = np.array([
            max(color[0], 188),
            max(color[1], color[0] - 22),
            min(color[2], color[1] - 18),
        ], dtype=np.float32)
    return [int(v) for v in color]


def _ink_mark(crop: np.ndarray, shirt_color: list[int]) -> Image.Image:
    from scipy import ndimage

    luma = crop.astype(np.float32).mean(axis=2)
    cloth = float(np.percentile(luma, 72))
    ink = luma < cloth - 18
    ink = ndimage.binary_closing(ink, structure=np.ones((3, 3)), iterations=1)
    labeled, count = ndimage.label(ink)
    kept = np.zeros_like(ink)
    if count:
        sizes = sorted(((int((labeled == index).sum()), index) for index in range(1, count + 1)), reverse=True)
        kept |= labeled == sizes[0][1]
    if kept.sum() < 30:
        kept = ink
    ys, xs = np.nonzero(kept)
    if len(ys) > 20:
        cut = int(ys.min() + 0.62 * (ys.max() - ys.min()))
        kept[cut:] = False
        kept = ndimage.binary_opening(kept, iterations=1)
        kept = ndimage.binary_closing(kept, iterations=1)
        labeled, count = ndimage.label(kept)
        if count:
            pick = max(range(1, count + 1), key=lambda index: int((labeled == index).sum()))
            kept = labeled == pick
    canvas = np.full(crop.shape, np.array(shirt_color, dtype=np.uint8), dtype=np.uint8)
    canvas[kept] = (22, 26, 30)
    ys, xs = np.nonzero(kept)
    if len(ys) > 20:
        y0, y1 = int(ys.min()), int(ys.max())
        x0, x1 = int(xs.min()), int(xs.max())
        pad = 8
        y0 = max(0, y0 - pad)
        x0 = max(0, x0 - pad)
        y1 = min(canvas.shape[0] - 1, y1 + pad)
        x1 = min(canvas.shape[1] - 1, x1 + pad)
        canvas = canvas[y0:y1 + 1, x0:x1 + 1]
    return Image.fromarray(canvas)


def _jersey(color: list[int], size: int = 1024) -> np.ndarray:
    rng = np.random.default_rng(11)
    base = np.array(color, dtype=np.float32)
    rows = np.arange(size, dtype=np.float32)
    knit = (np.sin(rows[:, None] * 1.65) * np.sin(rows[None, :] * 0.42)) * 2.4
    haze = rng.normal(0, 1.4, (size, size)).astype(np.float32)
    return np.clip(base + knit[:, :, None] + haze[:, :, None], 0, 255).astype(np.uint8)


def _twill(color: list[int], size: int = 1024) -> np.ndarray:
    rng = np.random.default_rng(5)
    base = np.array(color, dtype=np.float32)
    rows = np.arange(size, dtype=np.float32)
    twill = np.sin((rows[:, None] + rows[None, :]) * 0.28) * 2.8
    haze = rng.normal(0, 1.8, (size, size)).astype(np.float32)
    return np.clip(base + twill[:, :, None] + haze[:, :, None], 0, 255).astype(np.uint8)


def _boundary(faces: np.ndarray) -> np.ndarray:
    edges: dict[tuple[int, int], int] = {}
    for a, b, c in faces:
        for i, j in ((int(a), int(b)), (int(b), int(c)), (int(c), int(a))):
            key = (i, j) if i < j else (j, i)
            edges[key] = edges.get(key, 0) + 1
    rim = {i for (i, j), count in edges.items() if count == 1 for i in (i, j)}
    return np.array(sorted(rim), dtype=np.int64)


def _even_rims(verts: np.ndarray, faces: np.ndarray, sleeves: bool = False) -> np.ndarray:
    rim = _boundary(faces)
    if len(rim) < 12:
        return verts
    out = verts.copy()
    y = out[:, 1]
    low = float(np.percentile(y[rim], 18))
    hem = rim[y[rim] <= low + 0.028]
    if len(hem) >= 8:
        out[hem, 1] = float(np.median(out[hem, 1]))
    high = float(np.percentile(y[rim], 86))
    neck = rim[y[rim] >= high - 0.012]
    if 8 <= len(neck) <= 80:
        out[neck, 1] = float(np.median(out[neck, 1]))
    if not sleeves:
        return out
    hem_y = float(out[hem, 1].min()) if len(hem) else float(y.min())
    arms = rim[(np.abs(out[rim, 0]) > 0.13) & (y[rim] > hem_y + 0.07) & (y[rim] < high - 0.04)]
    for side in (-1.0, 1.0):
        ring = arms[out[arms, 0] * side > 0]
        if len(ring) < 6:
            continue
        out[ring, 0] = float(np.median(out[ring, 0]))
        out[ring, 1] = 0.45 * out[ring, 1] + 0.55 * float(np.median(out[ring, 1]))
    return out


def _cut_smooth(body: Path, chosen, destination: Path, base_color: list[float], offset: float, min_faces: int = 80, sleeves: bool = False) -> None:
    from garment_job import _export_faces
    from pygltflib import GLTF2
    from skin_garments import body_skin
    from smplx_export import pack_glb, vertex_normals

    positions, joints, weights, names, parents, world = body_skin(body)
    gltf = GLTF2().load(str(body))
    faces = _export_faces(gltf, gltf.binary_blob(), gltf.meshes[0].primitives[0].indices)
    keep = np.zeros(len(positions), dtype=bool)
    keep[chosen] = True
    kept_faces = faces[keep[faces].all(axis=1)]
    if len(kept_faces) < min_faces:
        raise RuntimeError("That garment region has no surface.")
    used = np.unique(kept_faces)
    remap = np.full(len(positions), -1, dtype=np.int64)
    remap[used] = np.arange(len(used))
    body_normals = vertex_normals(positions, faces)
    cloth = positions[used] + body_normals[used] * np.float32(offset)
    local = remap[kept_faces]
    cloth = _even_rims(cloth, local, sleeves=sleeves)
    pack_glb(
        cloth,
        vertex_normals(cloth, local),
        joints[used],
        weights[used],
        local,
        names,
        parents,
        world,
        destination,
        base_color=base_color,
    )


def _logo(image: np.ndarray, labels: np.ndarray, shirt_color: list[int]) -> dict | None:
    from scipy import ndimage

    upper = labels == UPPER
    if upper.sum() < 200:
        return None
    x0, y0, x1, y1 = _span(upper)
    chest = np.zeros_like(upper)
    chest[y0 + int((y1 - y0) * 0.06):y0 + int((y1 - y0) * 0.52), x0 + int((x1 - x0) * 0.30):x0 + int((x1 - x0) * 0.70)] = True
    luma = image.astype(np.float32).mean(axis=2)
    cloth_luma = float(np.median(luma[upper]))
    ink = chest & upper & (luma < cloth_luma - 28)
    labeled, count = ndimage.label(ink)
    if count == 0:
        return None
    sizes = [(int((labeled == index).sum()), index) for index in range(1, count + 1)]
    sizes.sort(reverse=True)
    kept = np.zeros_like(ink)
    for size, index in sizes[:4]:
        if size < 30:
            continue
        kept |= labeled == index
    if kept.sum() < 40:
        return None
    gx0, gy0, gx1, gy1 = _span(kept)
    pad_x = max(6, int((gx1 - gx0) * 0.10))
    pad_y = max(6, int((gy1 - gy0) * 0.16))
    gx0 = max(x0, gx0 - pad_x)
    gy0 = max(y0, gy0 - pad_y)
    gx1 = min(x1, gx1 + pad_x)
    gy1 = min(y1, gy1 + pad_y)
    crop = image[gy0:gy1 + 1, gx0:gx1 + 1].copy()
    return {
        "image": Image.fromarray(crop),
        "mark": _ink_mark(crop, shirt_color),
        "box": {
            "x0": 0.355,
            "x1": 0.645,
            "y0": 0.175,
            "y1": 0.355,
        },
    }


def extract(front: Path, dest: Path) -> dict:
    dest.mkdir(parents=True, exist_ok=True)
    image, labels = _segment(front)
    edges = _person(image, labels)
    edges["shirt_color"] = _shirt_color(image, labels)
    edges["pants_color"] = _pants_color(image, labels)
    logo = _logo(image, labels, edges["shirt_color"])
    if logo is not None:
        logo["image"].save(dest / "logo_raw.png")
        logo["mark"].save(dest / "logo.png")
        edges["logo"] = logo["box"]
    (dest / "edges.json").write_text(json.dumps(edges, indent=2), encoding="utf-8")
    return edges


def apply_fit(body: Path, work: Path, shirt_out: Path, pants_out: Path) -> None:
    from garment_job import _joint_weights
    from skin_garments import body_skin
    from texture_samples import _pack

    edges = json.loads((work / "edges.json").read_text(encoding="utf-8"))
    positions, joints, weights, names, parents, world = body_skin(body)
    labels = [str(name or "").lower() for name in names]
    feet_y = float(positions[:, 1].min())
    span = float(positions[:, 1].max()) - feet_y

    def height(name: str) -> float:
        return feet_y + edges[name] * span

    shirt_hem = height("shirt_hem") - 0.07
    pants_hem = max(feet_y + 0.02, height("pants_hem") - 0.03)
    pants_top = max(height("pants_top") + 0.06, shirt_hem + 0.16)
    torso = {
        "spine1", "spine2", "spine3", "spine",
        "left_collar", "right_collar",
        "left_shoulder", "right_shoulder",
    }
    blocked = {
        "neck", "head", "jaw", "left_eye_smplhf", "right_eye_smplhf",
        "left_foot", "right_foot",
        "left_wrist", "right_wrist",
        "left_hand", "right_hand",
        "left_knee", "right_knee",
    }
    elbow_w = _joint_weights(joints, weights, labels, {"left_elbow", "right_elbow"})
    if edges.get("long_sleeve"):
        torso |= {"left_elbow", "right_elbow"}
    torso_w = _joint_weights(joints, weights, labels, torso)
    blocked_w = _joint_weights(joints, weights, labels, blocked)
    pelvis_w = _joint_weights(joints, weights, labels, {"pelvis"})
    hip_w = _joint_weights(joints, weights, labels, {"left_hip", "right_hip"})
    shoulder_w = _joint_weights(joints, weights, labels, {"left_shoulder", "right_shoulder"})
    sleeve_ok = (elbow_w < 0.62) if not edges.get("long_sleeve") else True
    shirt = np.flatnonzero(
        (positions[:, 1] > shirt_hem)
        & (blocked_w < 0.48)
        & sleeve_ok
        & (
            (torso_w >= 0.12)
            | ((pelvis_w >= 0.06) & (positions[:, 1] > shirt_hem))
            | ((hip_w >= 0.08) & (positions[:, 1] > shirt_hem))
            | ((shoulder_w >= 0.10) & (positions[:, 1] > shirt_hem + 0.02))
        )
    )
    shirt_rgb = [value / 255 for value in edges["shirt_color"]]
    _cut_smooth(body, shirt, shirt_out, [*shirt_rgb, 1], 0.006, sleeves=True)
    legs = {"left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle", "pelvis"}
    leg_w = _joint_weights(joints, weights, labels, legs)
    foot_w = _joint_weights(joints, weights, labels, {"left_foot", "right_foot"})
    pants = np.flatnonzero(
        (leg_w >= 0.12)
        & (foot_w < 0.42)
        & (positions[:, 1] > pants_hem)
        & (positions[:, 1] < pants_top + 0.05)
    )
    pants_rgb = [value / 255 for value in edges["pants_color"]]
    _cut_smooth(body, pants, pants_out, [*pants_rgb, 1], 0.0045, min_faces=40)

    albedo = _jersey(edges["shirt_color"])
    logo_path = work / "logo_raw.png"
    if not logo_path.is_file():
        logo_path = work / "logo.png"
    if logo_path.is_file() and edges.get("logo"):
        box = {
            "x0": 0.355,
            "x1": 0.645,
            "y0": 0.175,
            "y1": 0.355,
        }
        front = Image.fromarray(albedo[:, :512])
        width = max(int((box["x1"] - box["x0"]) * 512), 8)
        height_px = max(int((box["y1"] - box["y0"]) * 1024), 8)
        stamp = _ink_mark(np.asarray(Image.open(logo_path).convert("RGB")), edges["shirt_color"])
        stamp = stamp.resize((width, height_px), Image.Resampling.LANCZOS)
        front.paste(stamp, (int(box["x0"] * 512), int(box["y0"] * 1024)))
        albedo[:, :512] = np.asarray(front)
    _pack(shirt_out, Image.fromarray(albedo), 0)
    _pack(pants_out, Image.fromarray(_twill(edges["pants_color"])), 0)


if __name__ == "__main__":
    extract(Path(sys.argv[1]), Path(sys.argv[2]))
