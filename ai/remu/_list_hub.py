from huggingface_hub import HfApi

api = HfApi()
repos = [
    "Co2y/UP2You",
    "hohs/SiTH-diffusion-1K",
    "alimama-creative/SD3-Controlnet-Inpainting",
    "InstantX/SD3-Controlnet-Pose",
]
for repo in repos:
    print("==", repo)
    total = 0
    for item in api.list_repo_tree(repo, recursive=True):
        size = getattr(item, "size", None) or 0
        total += size
        if size > 20_000_000:
            print(f"  {size/1e9:.2f} GB  {item.path}")
    print(f"  TOTAL {total/1e9:.2f} GB")
