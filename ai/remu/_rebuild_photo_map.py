from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai"))
sys.path.insert(0, str(ROOT / "ai" / "remu"))

from photo_map import apply_fit

WEB = ROOT / "avatar_studio" / "web"
WORK = WEB / "garments" / "saved" / "garment_job" / "photo_map"
BODY = WEB / "smplx_thin.glb"
SHIRT = WEB / "garments" / "fitted.glb"
PANTS = WEB / "garments" / "pants.glb"
apply_fit(BODY, WORK, SHIRT, PANTS)
saved = WEB / "garments" / "saved" / "auto_test"
saved.mkdir(parents=True, exist_ok=True)
(saved / "shirt.glb").write_bytes(SHIRT.read_bytes())
(saved / "pants.glb").write_bytes(PANTS.read_bytes())
print("rebuilt", SHIRT, PANTS)
