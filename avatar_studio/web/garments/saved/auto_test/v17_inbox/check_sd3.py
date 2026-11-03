import os

os.environ["HF_HOME"] = "/home/nadhir/remu/hf"
from huggingface_hub import hf_hub_download

try:
    hf_hub_download("stabilityai/stable-diffusion-3-medium-diffusers", "model_index.json")
    print("SD3_ACCESS=yes")
except Exception as error:
    print(type(error).__name__)
    print(str(error).splitlines()[0][:240])
