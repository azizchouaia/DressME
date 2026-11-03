"""Send the shirt layer and the pants layer through the same T4 reconstruct, then save them."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai" / "remu"))

from garment_job import DATASET, JOB, WEB, _download, _push_dataset, _push_kernel, _wait, _wait_until_idle, _wear_reco, mark

BODY = WEB / "smplx_thin.glb"
AUTO = WEB / "garments" / "saved" / "auto_test"


def main() -> None:
    mark("Auto test", "Shirt layer and pants layer, same reconstruct as the working outfit.")
    _push_dataset(JOB / "dataset")
    _wait_until_idle()
    _push_kernel()
    _wait()
    _download()
    meshes = list((JOB / "mesh").rglob("*_reco.obj"))
    lower = [path for path in meshes if "ower" in path.name]
    shirt = [path for path in meshes if "garment_reco" in path.name and "ower" not in path.name]
    if not lower or not shirt:
        raise RuntimeError(f"The T4 did not return both layers: {[path.name for path in meshes]}")
    shirt_url = _wear_reco(shirt[-1], BODY, {"top": "short_sleeves", "bottom": "pants"}, [0.78, 0.95, 0.12, 1])
    pants_url = _wear_reco(lower[-1], BODY, {"top": "short_sleeves", "bottom": "pants"}, [0.70, 0.64, 0.48, 1])
    AUTO.mkdir(parents=True, exist_ok=True)
    for url, name in ((shirt_url, "shirt.glb"), (pants_url, "pants.glb")):
        source = WEB / url.lstrip("/")
        target = AUTO / name
        target.write_bytes(source.read_bytes())
        print("saved", target)
    mark("Auto test is saved", "Shirt and pants are in garments/saved/auto_test.", busy=False, mesh="/garments/saved/auto_test/shirt.glb")


if __name__ == "__main__":
    main()
