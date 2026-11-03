import json
from pathlib import Path

path = Path(r"C:\Users\NADHIR\Desktop\Dressme\ai\remu\kaggle_kernel\dressme-high-res-clothes.ipynb")
nb = json.loads(path.read_text(encoding="utf-8"))
src = "".join(nb["cells"][1]["source"])
old = """candidates = [
    Path('/kaggle/working/inputs'),
    Path('inputs'),
    Path('/kaggle/input/dressme-remu-inputs'),
]
src = next((item for item in candidates if (item / 'templates' / 'smplx_canonical.obj').is_file()), None)
if src is None:
    hits = []
    for root_dir in (Path('/kaggle/working'), Path('/kaggle/input')):
        if root_dir.exists():
            hits.extend(root_dir.rglob('smplx_canonical.obj'))
    if not hits:
        raise FileNotFoundError('smplx_canonical.obj was not uploaded with the notebook')
    src = hits[0].parent.parent
"""
new = """src = None
for root_dir in (Path('/kaggle/input'), Path('/kaggle/working'), Path('.')):
    if not root_dir.exists():
        continue
    for image in root_dir.rglob('shirt.png'):
        folder = image.parents[1]
        if image.parent.name == 'images' and (folder / 'templates' / 'smplx_canonical.obj').is_file():
            src = folder
            break
    if src is not None:
        break
if src is None:
    raise FileNotFoundError('shirt.png was not uploaded with the notebook')
"""
shoes = """# This run builds the shoe layer only. Shirt, shorts, and vest stay in the dataset.
keep = 'Shoes'
for folder in ('images', 'back_images', 'smplx'):
    for item in (test / folder).iterdir():
        if keep not in item.name:
            item.unlink()
"""
if old not in src or shoes not in src:
    raise SystemExit('notebook pattern missing')
src = src.replace(old, new).replace(shoes, "")
nb["cells"][1]["source"] = [line + "\n" for line in src.split("\n")]
if nb["cells"][1]["source"]:
    nb["cells"][1]["source"][-1] = nb["cells"][1]["source"][-1].rstrip("\n")
path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
meta = json.loads(Path(r"C:\Users\NADHIR\Desktop\Dressme\ai\remu\kaggle_kernel\kernel-metadata.json").read_text(encoding="utf-8"))
meta["dataset_sources"] = ["nadhirmaamar/dressme-shirt-photo"]
Path(r"C:\Users\NADHIR\Desktop\Dressme\ai\remu\kaggle_kernel\kernel-metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
print("patched")
