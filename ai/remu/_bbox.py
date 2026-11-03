from pathlib import Path

def bounds(path):
    p = Path(path)
    mn = [1e9, 1e9, 1e9]
    mx = [-1e9, -1e9, -1e9]
    n = 0
    for line in p.open(encoding="utf-8", errors="ignore"):
        if not line.startswith("v "):
            continue
        x, y, z = map(float, line.split()[1:4])
        for i, v in enumerate((x, y, z)):
            mn[i] = min(mn[i], v)
            mx[i] = max(mx[i], v)
        n += 1
    print(p.name, "verts", n)
    print("  min", [round(v, 3) for v in mn])
    print("  max", [round(v, 3) for v in mx])

bounds(r"C:\Users\NADHIR\Desktop\Dressme\avatar_studio\web\garments\saved\kaggle\meshes_384\00127_Outer_reco.obj")
