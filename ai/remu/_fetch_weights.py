"""Download the public ReMu weights into the WSL checkout. SMPL-X stays the official npz."""
from pathlib import Path

from huggingface_hub import snapshot_download

ROOT = Path.home() / "remu" / "ReMu"
CKPT = ROOT / "checkpoints"
official = ROOT / "body_models" / "smplx" / "SMPLX_NEUTRAL.npz"

jobs = [
    (
        "Co2y/UP2You",
        CKPT / "up2you",
        ["human_models/models/smplx/SMPLX_NEUTRAL.npz", "human_models/models/smplx/SMPLX_NEUTRAL.pkl"],
    ),
    ("hohs/SiTH-diffusion-1K", CKPT / "sith" / "diffusion", None),
    ("alimama-creative/SD3-Controlnet-Inpainting", CKPT / "sd3" / "inpaint", None),
    ("InstantX/SD3-Controlnet-Pose", CKPT / "sd3" / "pose", None),
]

for repo, dest, ignore in jobs:
    dest.mkdir(parents=True, exist_ok=True)
    print("START", repo, flush=True)
    snapshot_download(repo, local_dir=str(dest), ignore_patterns=ignore)
    print("DONE", repo, flush=True)

link = CKPT / "up2you" / "human_models" / "models" / "smplx" / "SMPLX_NEUTRAL.npz"
link.parent.mkdir(parents=True, exist_ok=True)
if official.is_file() and not link.exists():
    link.symlink_to(official)
    print("LINKED official SMPL-X", official, flush=True)
elif link.exists():
    print("SMPL-X already present", link, flush=True)
else:
    print("MISSING official SMPL-X at", official, flush=True)

print("PUBLIC_WEIGHTS_DONE", flush=True)
