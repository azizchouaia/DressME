from huggingface_hub import HfApi

api = HfApi()
repos = [
    "Co2y/UP2You",
    "hohs/SiTH-diffusion-1K",
    "stabilityai/stable-diffusion-3-medium-diffusers",
    "alimama-creative/SD3-Controlnet-Inpainting",
    "InstantX/SD3-Controlnet-Pose",
]
for repo in repos:
    try:
        info = api.model_info(repo)
        print(repo, "gated=", info.gated, "private=", info.private)
    except Exception as exc:
        print(repo, "ERR", type(exc).__name__, str(exc)[:200])
