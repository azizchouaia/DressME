from pathlib import Path
from huggingface_hub import snapshot_download

root = Path.home() / "remu" / "ReMu" / "checkpoints"
sd3 = root / "sd3" / "medium"
sd3.mkdir(parents=True, exist_ok=True)
print("START stabilityai/stable-diffusion-3-medium-diffusers", flush=True)
try:
    snapshot_download("stabilityai/stable-diffusion-3-medium-diffusers", local_dir=str(sd3))
    print("DONE sd3", flush=True)
except Exception as exc:
    print("SD3_BLOCKED", type(exc).__name__, str(exc)[:400], flush=True)

sd21 = root / "up2you" / "sd21"
sd21.mkdir(parents=True, exist_ok=True)
print("START stabilityai/stable-diffusion-2-1-base", flush=True)
snapshot_download("stabilityai/stable-diffusion-2-1-base", local_dir=str(sd21))
print("DONE sd21", flush=True)
