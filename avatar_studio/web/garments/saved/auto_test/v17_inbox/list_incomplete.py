import os

root = "/home/nadhir/remu/hf/hub/models--stabilityai--stable-diffusion-3-medium-diffusers"
for folder, _, names in os.walk(root):
    for name in names:
        if name.endswith(".incomplete"):
            path = os.path.join(folder, name)
            print(round(os.path.getsize(path) / 1e6), "MB", name[:24])
