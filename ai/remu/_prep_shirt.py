"""Turn the product photo into the one SiTH layer this Kaggle run will build."""
from pathlib import Path
import shutil

from PIL import Image

root = Path(r"C:\Users\NADHIR\Desktop\Dressme\ai\remu\shirt_input")
src = Path(r"C:\Users\NADHIR\.cursor\projects\c-Users-NADHIR-Desktop-Dressme\assets\image-8451d9a5-a0df-4efa-a53c-6428b5e9bb69.jpg")
body = root / "templates" / "smplx_canonical.obj"

image = Image.open(src).convert("RGBA")
pixels = image.getdata()
out = []
for r, g, b, a in pixels:
    if r > 245 and g > 245 and b > 245:
        out.append((r, g, b, 0))
    else:
        out.append((r, g, b, 255))
image.putdata(out)

for folder in ("images", "back_images", "smplx"):
    (root / folder).mkdir(parents=True, exist_ok=True)
image.save(root / "images" / "shirt.png")
image.save(root / "back_images" / "shirt.png")
shutil.copyfile(body, root / "smplx" / "shirt_smplx.obj")
print("ready", image.size)
