"""Front and back photo to a shirt and pants on the avatar, through SiTH on a Kaggle T4.

    py -3 ai/remu/garment_pipeline.py FRONT BACK [--mirror-front] [--skip-kaggle] [--avatar NAME] [--gender male|female]

--mirror-front undoes a selfie camera. --skip-kaggle reuses the last download.
--avatar NAME also saves the person's face, hair colour, skin tone, and the
picked hairstyle as the avatar avatars/NAME/avatar.glb; that is done
once, later outfits fit the same avatar.
The garments land in avatar_studio/web/garments/saved/reco; open the viewer with
?mesh=/smplx_thin.glb&wear=reco to see them.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "ai" / "remu"))

from garment_inputs import prepare  # noqa: E402

WORK = ROOT / "avatar_studio" / "web" / "garments" / "saved" / "pipeline"
DATASET_DIR = WORK / "dataset"
RUN_DIR = WORK / "run"
KERNEL_DIR = ROOT / "ai" / "remu" / "kaggle_outfit"
DATASET_ID = "nadhirmaamar/dressme-garment-photos"
KERNEL_ID = "nadhirmaamar/dressme-outfit-pipeline"
PYTHON = ROOT / "ai" / "vendor" / "TripoSR" / ".venv" / "Scripts" / "python.exe"
OUTPUTS = r"^(outfit_reco\.obj|outfit_smplx\.obj|fit/.*)$"


def _kaggle(args: list[str]) -> str:
    env = {**os.environ, "PYTHONUTF8": "1"}
    result = subprocess.run(["py", "-3", "-m", "kaggle", *args], cwd=str(ROOT), env=env, text=True, encoding="utf-8", errors="replace", capture_output=True)
    output = (result.stdout or "") + (result.stderr or "")
    if result.returncode != 0:
        raise RuntimeError(output.strip() or f"kaggle {' '.join(args)} failed")
    return output.strip()


def _say(text: str) -> None:
    print(time.strftime("%H:%M:%S"), text, flush=True)


def push_dataset() -> None:
    if DATASET_ID.split("/")[1] in _kaggle(["datasets", "list", "-m", "--csv"]):
        _kaggle(["datasets", "version", "-p", str(DATASET_DIR), "-m", "New front and back photos", "-r", "zip"])
    else:
        _kaggle(["datasets", "create", "-p", str(DATASET_DIR), "-r", "zip"])
    for _ in range(40):
        if "ready" in _kaggle(["datasets", "status", DATASET_ID]):
            return
        time.sleep(15)
    raise RuntimeError("The photo dataset did not become ready on Kaggle.")


def push_kernel() -> None:
    """Attach the previous run's output so the GPU stack is copied instead of rebuilt."""
    meta_path = KERNEL_DIR / "kernel-metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["kernel_sources"] = [KERNEL_ID]
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    try:
        _kaggle(["kernels", "push", "-p", str(KERNEL_DIR)])
    except RuntimeError:
        meta["kernel_sources"] = []
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        _kaggle(["kernels", "push", "-p", str(KERNEL_DIR)])


def wait_for_kernel() -> None:
    while True:
        time.sleep(60)
        try:
            status = _kaggle(["kernels", "status", KERNEL_ID])
        except RuntimeError as exc:
            _say(f"status check failed: {str(exc).splitlines()[-1][:160]}")
            continue
        _say(status.splitlines()[-1])
        if "COMPLETE" in status:
            return
        if "ERROR" in status or "CANCEL" in status:
            raise RuntimeError(f"The Kaggle run stopped: {status}. Log: https://www.kaggle.com/code/{KERNEL_ID}")


def download() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    for attempt in range(5):
        try:
            _kaggle(["kernels", "output", KERNEL_ID, "-p", str(RUN_DIR), "--file-pattern", OUTPUTS, "--page-size", "200", "-o", "-q"])
            break
        except RuntimeError as exc:
            _say(f"download attempt {attempt + 1} failed: {str(exc).splitlines()[-1][:160]}")
            time.sleep(20 * (attempt + 1))
    missing = [name for name in ("outfit_reco.obj", "outfit_smplx.obj") if not (RUN_DIR / name).is_file()]
    if missing:
        raise RuntimeError(f"The Kaggle output has no {', '.join(missing)}.")


def main() -> None:
    flags = sys.argv[1:]
    avatar = flags[flags.index("--avatar") + 1] if "--avatar" in flags else None
    gender = flags[flags.index("--gender") + 1] if "--gender" in flags else None
    args = [a for a in flags if not a.startswith("--") and a not in (avatar, gender)]
    if "--skip-kaggle" not in sys.argv:
        _say("checking and framing the photos")
        _say(json.dumps(prepare(Path(args[0]), Path(args[1]), DATASET_DIR, DATASET_ID, "--mirror-front" in sys.argv)))
        _say("uploading the photos")
        push_dataset()
        _say(f"starting the T4: https://www.kaggle.com/code/{KERNEL_ID}")
        push_kernel()
        wait_for_kernel()
        _say("downloading the outfit mesh and the fitted body")
        download()
    _say("cutting the shirt and pants and fitting them to the avatar")
    subprocess.check_call([str(PYTHON), str(ROOT / "ai" / "remu" / "reco_garments.py"), str(RUN_DIR), str(DATASET_DIR)], cwd=str(ROOT))
    mesh = "/smplx_thin.glb"
    if avatar:
        _say("picking the hairstyle from the photos")
        subprocess.check_call([sys.executable, str(ROOT / "ai" / "remu" / "hair_look.py"), str(DATASET_DIR), *(["--gender", gender] if gender else [])], cwd=str(ROOT))
        _say(f"saving the face and skin tone as the avatar {avatar}")
        subprocess.check_call([str(PYTHON), str(ROOT / "ai" / "remu" / "photo_avatar.py"), str(RUN_DIR), str(DATASET_DIR), avatar], cwd=str(ROOT))
        mesh = f"/avatars/{avatar}/avatar.glb"
    _say(f"done: open the viewer with ?mesh={mesh}&wear=reco")


if __name__ == "__main__":
    main()
