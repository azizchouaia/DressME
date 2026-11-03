"""Send one loafer from the local photo to the TripoSR server."""

from pathlib import Path

import numpy as np
import urllib.request
from PIL import Image
from scipy import ndimage

PHOTO = Path(r"C:\Users\NADHIR\Desktop\clothes\shoes.avif")
OUT = Path(r"C:\Users\NADHIR\Desktop\Dressme\avatar_studio\web\garments\shoe_scan.jpg")
GLB = Path(r"C:\Users\NADHIR\Desktop\Dressme\avatar_studio\web\garments\shoe_scan.glb")

image = np.asarray(Image.open(PHOTO).convert("RGB"))
# One loafer only: the side view, with the second shoe and the green wall removed.
navy = (image[:, :, 2] > image[:, :, 0] + 12) & (image[:, :, 2] >= image[:, :, 1] - 8) & (image[:, :, 0] < 140)
brown = (image[:, :, 0] > image[:, :, 2] + 25) & (image[:, :, 0] < 190) & (image[:, :, 1] > 35) & (image[:, :, 2] < 130)
sole = image.mean(axis=2) < 55
mask = ndimage.binary_dilation(navy | brown | sole, iterations=2)
mask[:200, :] = False
mask[330:, :] = False
ys, xs = np.where(mask)
cut = image[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
cut_mask = mask[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
cut = cut.copy()
cut[~cut_mask] = 255
Image.fromarray(cut).save(OUT, quality=95)
print("crop", cut.shape, OUT)

request = urllib.request.Request(
    "http://127.0.0.1:8766/reconstruct",
    data=OUT.read_bytes(),
    headers={"Content-Type": "image/jpeg", "X-TripoSR-Resolution": "256", "X-TripoSR-Object": "1"},
    method="POST",
)
with urllib.request.urlopen(request, timeout=300) as response:
    GLB.write_bytes(response.read())
print("glb", GLB.stat().st_size)
