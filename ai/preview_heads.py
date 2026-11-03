import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / "avatar_studio" / "web"
SIZE = 360
CENTRE = np.array([float(os.environ.get("PREVIEW_X", 0.0)), float(os.environ.get("PREVIEW_Y", 1.58)), 0.0])
HALF = float(os.environ.get("PREVIEW_HALF", 0.17))
TINT = (0.28, 0.18, 0.11)


def load(path):
    scene = trimesh.load(path, force="scene")
    parts = []
    for geom in scene.dump():
        verts = np.asarray(geom.vertices)
        uv = getattr(geom.visual, "uv", None)
        image = None
        material = getattr(geom.visual, "material", None)
        if material is not None:
            image = getattr(material, "baseColorTexture", None)
        parts.append((verts, geom.faces, uv, None if image is None else np.asarray(image.convert("RGBA")) / 255.0))
    return parts


def rotate(verts, yaw):
    c, s = np.cos(yaw), np.sin(yaw)
    out = verts - CENTRE
    return np.stack([c * out[:, 0] + s * out[:, 2], out[:, 1], -s * out[:, 0] + c * out[:, 2]], 1)


def draw(layers, yaw):
    depth = np.full((SIZE, SIZE), -np.inf)
    color = np.full((SIZE, SIZE, 3), 0.96)
    light = np.array([0.3, 0.5, 0.8])
    light /= np.linalg.norm(light)
    for verts, faces, uv, image, tint in layers:
        view = rotate(verts, yaw)
        px = (view[:, 0] / HALF * 0.5 + 0.5) * SIZE
        py = (0.5 - view[:, 1] / HALF * 0.5) * SIZE
        tri = view[faces]
        normal = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
        normal /= np.linalg.norm(normal, axis=1, keepdims=True) + 1e-12
        for index, face in enumerate(faces):
            xs, ys = px[face], py[face]
            x0, x1 = int(max(0, np.floor(xs.min()))), int(min(SIZE - 1, np.ceil(xs.max())))
            y0, y1 = int(max(0, np.floor(ys.min()))), int(min(SIZE - 1, np.ceil(ys.max())))
            if x0 > x1 or y0 > y1:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            area = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
            if abs(area) < 1e-9:
                continue
            w1 = ((gx - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (gy - ys[0])) / area
            w2 = ((xs[1] - xs[0]) * (gy - ys[0]) - (gx - xs[0]) * (ys[1] - ys[0])) / area
            w0 = 1 - w1 - w2
            inside = (w0 >= 0) & (w1 >= 0) & (w2 >= 0)
            if not inside.any():
                continue
            z = w0 * view[face[0], 2] + w1 * view[face[1], 2] + w2 * view[face[2], 2]
            rows, cols = gy[inside].astype(int), gx[inside].astype(int)
            zz = z[inside]
            shade = 0.35 + 0.65 * abs(normal[index] @ light)
            rgb = np.tile(np.array(tint) * shade, (len(zz), 1))
            if image is not None and uv is not None:
                u = w0[inside] * uv[face[0], 0] + w1[inside] * uv[face[1], 0] + w2[inside] * uv[face[2], 0]
                v = w0[inside] * uv[face[0], 1] + w1[inside] * uv[face[1], 1] + w2[inside] * uv[face[2], 1]
                h, w = image.shape[:2]
                texel = image[np.clip(((1 - v) % 1) * h, 0, h - 1).astype(int), np.clip((u % 1) * w, 0, w - 1).astype(int)]
                keep = texel[:, 3] >= 0.5
                rows, cols, zz = rows[keep], cols[keep], zz[keep]
                rgb = (texel[keep, :3] * np.array(tint) * shade)
            front = zz > depth[rows, cols]
            depth[rows[front], cols[front]] = zz[front]
            color[rows[front], cols[front]] = rgb[front]
    return (np.clip(color, 0, 1) * 255).astype(np.uint8)


def in_window(verts, faces):
    y = verts[faces][:, :, 1]
    return faces[(y.max(1) > CENTRE[1] - HALF - 0.02) & (y.min(1) < CENTRE[1] + HALF + 0.02)]

def main():
    hair, beard, out = sys.argv[1], sys.argv[2], sys.argv[3]
    """preview_heads.py OUT BODY [WORN ...], paths relative to avatar_studio/web.
    Hair GLBs are tinted brown; other textured GLBs keep their own colours."""
    out, body, worn = sys.argv[1], sys.argv[2], sys.argv[3:]
    layers = []
    for path in [body, *worn]:
        tinted = path.startswith("hair/")
        for verts, faces, uv, image in load(ROOT / path):
            if image is not None and not tinted:
                image = image.copy()
                image[..., 3] = np.where(image[..., 3] > 0, 1.0, 0.0)
            tint = TINT if tinted else (1.0, 1.0, 1.0) if image is not None else (0.85, 0.68, 0.58)
            layers.append((verts, in_window(verts, faces), uv, image, tint))
    views = [draw(layers, yaw) for yaw in (0.0, np.pi / 2.2, np.pi)]
    Image.fromarray(np.concatenate(views, 1)).save(out)


if __name__ == "__main__":
    main()
