from huggingface_hub import hf_hub_download

for repo in (
    "alimama-creative/SD3-Controlnet-Inpainting",
    "InstantX/SD3-Controlnet-Pose",
):
    try:
        hf_hub_download(repo, "config.json")
        print(repo, "ok")
    except Exception as error:
        print(repo, type(error).__name__, str(error).splitlines()[0][:180])
