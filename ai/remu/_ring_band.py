from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))
from skin_garments import body_skin
from pygltflib import GLTF2
import numpy as np

body = ROOT / "avatar_studio" / "web" / "users" / "test-it.glb"
positions, joints, weights, names, parents, world = body_skin(body)
labels = [str(name or "") for name in names]
for index, label in enumerate(labels):
    low = label.lower()
    if "ring" in low or "index" in low or "middle" in low or "pinky" in low or "thumb" in low or "wrist" in low:
        print(index, label, [round(float(v), 4) for v in world[index]])

def weight_for(name):
    total = np.zeros(len(weights), dtype=np.float32)
    target = labels.index(name) if name in labels else labels.index(name.lower()) if name.lower() in [l.lower() for l in labels] else None
    # match exact lower
    ids = [i for i, label in enumerate(labels) if label.lower() == name.lower()]
    total = np.zeros(len(weights), dtype=np.float32)
    for slot in range(joints.shape[1]):
        for index in ids:
            total += np.where(joints[:, slot] == index, weights[:, slot], 0)
    return total

for name in ("left_ring1", "left_ring2", "left_ring3"):
    w = weight_for(name)
    print(name, "verts>=0.4", int((w >= 0.4).sum()), ">=0.2", int((w >= 0.2).sum()))
