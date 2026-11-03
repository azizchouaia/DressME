"""Paint the product shirt's white cloth and red mark onto the avatar shirt."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PHOTO = Path(
    r"C:\Users\NADHIR\.cursor\projects\c-Users-NADHIR-Desktop-Dressme\assets"
    r"\c__Users_NADHIR_AppData_Roaming_Cursor_User_workspaceStorage_8708a19794694fff80c94be4e708e8d4_images_1800147816_0340_0340-fa7a1d8f-83fe-4d84-9347-1ffafa2e7a0a.jpg"
)
ALBEDO = ROOT / "avatar_studio" / "web" / "garments" / "textured" / "shirt_albedo.png"
OBJ = ROOT / "avatar_studio" / "web" / "garments" / "textured" / "shirt.obj"


def garment_mask(width: int, height: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    faces = []
    for line in OBJ.read_text().splitlines():
        if not line.startswith("f "):
            continue
        corners = []
        for token in line.split()[1:]:
            point, tex, *_ = (token.split("/") + [""])[:2]
            corners.append(int(tex) - 1)
        faces.append(corners)
    uvs = []
    for line in OBJ.read_text().splitlines():
        if line.startswith("vt "):
            u, v = (float(part) for part in line.split()[1:3])
            uvs.append((u, v))
    uv = np.asarray(uvs, dtype=np.float32)

    def pixel(index: int) -> tuple[int, int]:
        u, v = uv[index]
        x = int(np.clip(u, 0, 0.999) * width)
        # The saved image is stored upright, matching the viewer.
        y = int(np.clip(1.0 - v, 0, 0.999) * height)
        return x, y

    for a, b, c in faces:
        xs = [pixel(a)[0], pixel(b)[0], pixel(c)[0]]
        ys = [pixel(a)[1], pixel(b)[1], pixel(c)[1]]
        min_x, max_x = max(min(xs), 0), min(max(xs), width - 1)
        min_y, max_y = max(min(ys), 0), min(max(ys), height - 1)
        if max_x <= min_x or max_y <= min_y:
            continue
        tri = np.array([[xs[0], ys[0]], [xs[1], ys[1]], [xs[2], ys[2]]], dtype=np.float32)
        yy, xx = np.mgrid[min_y : max_y + 1, min_x : max_x + 1]
        points = np.stack([xx, yy], axis=-1).reshape(-1, 2).astype(np.float32)
        v0, v1, v2 = tri[0], tri[1], tri[2]
        den = (v1[1] - v2[1]) * (v0[0] - v2[0]) + (v2[0] - v1[0]) * (v0[1] - v2[1])
        if abs(den) < 1e-6:
            continue
        w0 = ((v1[1] - v2[1]) * (points[:, 0] - v2[0]) + (v2[0] - v1[0]) * (points[:, 1] - v2[1])) / den
        w1 = ((v2[1] - v0[1]) * (points[:, 0] - v2[0]) + (v0[0] - v2[0]) * (points[:, 1] - v2[1])) / den
        w2 = 1 - w0 - w1
        inside = (w0 >= -0.01) & (w1 >= -0.01) & (w2 >= -0.01)
        hit = points[inside].astype(int)
        mask[hit[:, 1], hit[:, 0]] = True
    return mask


def main() -> None:
    albedo = np.asarray(Image.open(ALBEDO).convert("RGB")).astype(np.float32)
    photo = np.asarray(Image.open(PHOTO).convert("RGB"))
    height, width = albedo.shape[:2]
    mask = garment_mask(width, height)
    white = np.array([236, 238, 242], dtype=np.float32)
    albedo[mask] = albedo[mask] * 0.18 + white * 0.82

    red = (photo[:, :, 0] > 150) & (photo[:, :, 1] < 80) & (photo[:, :, 2] < 90)
    ys, xs = np.where(red)
    if len(xs) == 0:
        raise SystemExit("no red mark found in the photo")
    pad = 8
    crop = photo[
        max(ys.min() - pad, 0) : ys.max() + pad + 1,
        max(xs.min() - pad, 0) : xs.max() + pad + 1,
    ]
    crop_red = red[
        max(ys.min() - pad, 0) : ys.max() + pad + 1,
        max(xs.min() - pad, 0) : xs.max() + pad + 1,
    ]
    front = mask.copy()
    front[:, width // 2 :] = False
    fy, fx = np.where(front)
    top, bottom = int(fy.min()), int(fy.max())
    neck = fy < top + (bottom - top) * 0.18
    chest_x = int(np.median(fx[neck]))
    chest_y = int(top + (bottom - top) * 0.40)
    logo_h = int((bottom - top) * 0.46)
    scale = logo_h / crop.shape[0]
    logo_w = max(1, int(crop.shape[1] * scale))
    logo = np.asarray(Image.fromarray(crop).resize((logo_w, logo_h), Image.Resampling.LANCZOS))
    logo_alpha = np.asarray(
        Image.fromarray((crop_red.astype(np.uint8) * 255)).resize((logo_w, logo_h), Image.Resampling.LANCZOS)
    ).astype(np.float32) / 255.0
    x0 = chest_x - logo_w // 2
    y0 = chest_y - logo_h // 2
    for y in range(logo_h):
        for x in range(logo_w):
            yy, xx = y0 + y, x0 + x
            if yy < 0 or xx < 0 or yy >= height or xx >= width or logo_alpha[y, x] < 0.2:
                continue
            if not mask[yy, xx]:
                continue
            amount = float(logo_alpha[y, x])
            albedo[yy, xx] = albedo[yy, xx] * (1 - amount) + logo[y, x] * amount
    Image.fromarray(albedo.astype(np.uint8)).save(ALBEDO)
    print(f"painted chest at {chest_x},{chest_y} logo {logo_w}x{logo_h}")


if __name__ == "__main__":
    main()
