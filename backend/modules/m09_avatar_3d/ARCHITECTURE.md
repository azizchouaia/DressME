# M9 · Faceless avatar and worn clothes

Status as of 16 October 2026. The viewer runs locally. This file is the place to resume from. The binary meshes, the SMPL-X model, and the model weights are **not** in git. Reasons and paths are at the end.

## What is on screen

A faceless SMPL-X body in a Three.js viewer, with three skinned garments: a shirt, shorts, and a vest. They share the body skeleton. Pose chips move the sleeves and the legs with the body. Build sliders change body shape only, so they do not resize the clothes.

| Piece | File on the local machine | Role |
|---|---|---|
| Thin body | `avatar_studio/web/smplx_thin.glb` | Default body. Male. First three shape values `[-1.2, -2.0, 0.6]`. About 1.70 m tall, hip radius about 0.15 m. |
| Preserved body | `avatar_studio/web/smplx_body.glb` | The earlier body. Do not regenerate it. Shape values: `-1.27, -3.00, 3.00, 3.00, -0.03, 3.00, -2.07, -2.50, -0.19, 2.96`. |
| Shirt | `avatar_studio/web/garments/shirt.glb` | Inner layer of 4D-Dress subject 00127, fitted and skinned. |
| Shorts | `avatar_studio/web/garments/shorts.glb` | Lower layer, same subject. |
| Vest | `avatar_studio/web/garments/vest.glb` | Outer layer, same subject. It hangs off one shoulder. That is the saved mesh. |

Viewer pages, both under `avatar_studio/web/viewer/` in the local Dressme checkout (not this GitHub tree):

- `index.html` — build page. **Wear saved** loads the three GLBs.
- `clothes.html` — clothes only, so the build bar does not cover the head. It loads `/smplx_thin.glb` when the path ends with `clothes.html`.
- `scene.mjs?v=71` — the scene. Garment URLs use the same `?v=71` cache key.

Open the build page as `viewer/index.html?mesh=/smplx_thin.glb&v=71`. The local server that was used is `py -3 -m http.server 5290 --bind 127.0.0.1` with the working directory `avatar_studio/web`.

## Technology

| Layer | What | Why this one |
|---|---|---|
| Body model | SMPL-X, official NPZ from the Max Planck site, male | 10,475 vertices, 55 joints. Shape is blend shapes, not bone scale. |
| Body export | `ai/smplx_export.py` | Writes `smplx_thin.glb`. Does not overwrite `smplx_body.glb`. |
| Cloth reconstruction | SiTH `recon_model.pth` inside [ReMu](https://github.com/eth-ait/ReMu) (ETH, BMVC) | Turns a front photo and a back photo into a garment surface. |
| Registration | ReMu `knn_lbs` (`src/registration/canonicalize/knn_lbs.py`) | Puts the surface into the canonical rest pose of subject 00127. |
| Fit onto our body | `ai/remu/fit_baked.py` | One height scale, then a nearest-vertex offset. |
| Skinning | `ai/skin_garments.py`, `ai/skin_textured.py` | Copies the nearest body vertex's skin weights and packs the GLB. |
| Shirt color | `ai/apply_shirt_photo.py` | Paints a product photo onto `shirt_albedo.png`. Sleeves stay long. |
| Viewer | Three.js 0.186.1, `GLTFLoader`, `MeshStandardMaterial` | Clothes are `SkinnedMesh` children bound to the body skeleton. |

Not used for the picture that is on screen: Stable Diffusion 3 (still gated), UP2You, ContourCraft, TripoSR, and the user's own photos.

## Logic, in order

1. **Export the thin body.** Official male SMPL-X NPZ goes through `ai/smplx_export.py` to `smplx_thin.glb`. Shape controls in the viewer are morph targets. They do not move the clothes.

2. **Reconstruct the clothes.** Input is 4D-Dress subject 00127, not a photo of the user. Copies of the inputs live at `avatar_studio/web/garments/saved/kaggle/run_384/images/` and `back_images/`: `00127_Inner.png` (shirt), `00127_Lower.png` (shorts), `00127_Outer.png` (vest). SiTH runs on a Kaggle T4 at grid 384 (`ai/remu/kaggle_hires.py`, notebook `nadhirmaamar/dressme-high-res-clothes`). Surfaces land in `saved/kaggle/meshes_384/00127_{Inner,Lower,Outer}_reco.obj`.

3. **Canonicalize.** `ai/remu/kaggle_register.sh` calls ReMu `knn_lbs`. That step poses the shaped SMPL-X body of 00127, finds each garment vertex's nearest body vertex (`k=1`), inverts that vertex's linear-blend skinning matrix, and subtracts the pose blend shape. The garment is then in rest space, still on 00127's shape.

4. **Bake color.** `ai/remu/bake_kaggle.sh` writes albedo and normal maps.

5. **Move onto the thin body.** `fit_baked.py` does one global scale, not a per-region fit:

   `scale = height(smplx_thin) / height(00127 shaped rest)`

   `placed = thin[nearest] + (rest_garment - source[nearest]) * scale`

6. **Skin and pack.** `skin_garments.py` copies nearest-body skin weights. `skin_textured.py` packs `shirt.glb`, `shorts.glb`, `vest.glb` with the baked maps. `apply_shirt_photo.py` recolors the shirt from a product photo.

7. **Show.** `wearSaved()` in `scene.mjs` removes any mesh flagged `userData.garment`, then `addGarments()` loads the three GLBs. Skinned meshes are collected **before** they are added to the scene root. If the GLB has a color map or a normal map, the material color is white and those maps are kept. Otherwise the fallback colors are shirt `#c5c8cc`, shorts `#2c3140`, vest `#1a1c22`. Each mesh is `MeshStandardMaterial` with roughness 0.72, metalness 0, `DoubleSide`, `skinning: true`, `frustumCulled: false`, and `child.bind(body.skeleton, child.bindMatrix)`.

8. **Frame the body under the build bar.** On resize, the free band is between the bottom of `.build-bar` and the top of `.sheet` or `.clothes-dock`. The camera uses `setViewOffset` so the body sits in that band, and zoom is `min(1, free / (height * 0.86))`. Camera rest pose is position `(0, 0.95, 5.4)`, target `(0, 0.84, 0)`, field of view 34. Page colors are paper `#f6f4f0` and ink `#141414`. Skin material is `#d8cfc6`, roughness 0.62, metalness 0.02.

9. **Cloth follow-through** in `scene.mjs` is a spring on the hem. It is not a cloth simulator. Pose chips call `settleCloth()`.

## GPUs

Two machines, on purpose.

**Laptop, through WSL Ubuntu.** `ai/remu/setup_wsl.sh` targets compute capability 12.0 (`TORCH_CUDA_ARCH_LIST=12.0`), which is an RTX 50-series GPU. Stock ReMu pins torch 2.5.1 with CUDA 12.1. That build has no kernel for this chip, so the local env is torch **2.8.0+cu128**, the matching torchvision, kaolin, and nvdiffrast compiled with conda-forge nvcc 12.8. The env lives at `~/remu/env` inside WSL. The ReMu checkout is `~/remu/ReMu`. Large weights are kept on `D:\remu-weights` (and WSL links to that disk) so they do not fill `C:`.

This GPU can run the coarse demo. `ai/remu/demo_recon.sh` uses SiTH grid **192**. Grid **512** crashes WSL. Do not retry it on this machine.

**Kaggle, Tesla T4 (16 GB).** `ai/remu/kaggle_hires.py` sets `TORCH_CUDA_ARCH_LIST=7.5`. Each session starts empty, so the notebook installs Python 3.12 with `uv`, then torch 2.8.0 cu128, kaolin, and nvdiffrast, then clones ReMu and downloads `recon_model.pth` from `https://files.ait.ethz.ch/projects/SiTH/recon_model.pth` if it is not already in the working folder. Grid **384** is the run that produced the worn meshes. Grid **512** ran out of memory on the T4 as well. Do not retry 512 there either.

Kaggle is not required to *view* the clothes. The GLBs are already built. Kaggle is only required to reconstruct a new garment at grid 384. To avoid reinstalling, attach a private Kaggle dataset that already holds the venv, the ReMu checkout, and `recon_model.pth`, and copy those in instead of downloading. A persistent GPU pod with a disk (a T4, or a 24 GB card if 512 is ever retried) is the same idea outside Kaggle. The laptop env is already persistent. Its limit is memory, not the install.

## Current limits

- Sizing is one scale for the whole garment. A tighter waist or a longer sleeve is not fitted on its own.
- The build sliders do not refit clothes. Only the pose path does, because the garments are skinned.
- The vest hangs off one shoulder.
- Hem motion is a lag spring, not ContourCraft.
- The clothes are one example subject (00127), not a photo of the person using the app.
- There is no per-user avatar from a phone photo in this pipeline yet. UP2You was wired (`ai/remu/from_photo.sh`) and is not what produced these GLBs.
- SD3 is still access-gated for the Hugging Face account used here.
- SMPL-X files, exported body GLBs, 4D-Dress images, reconstructed OBJs, and weights must stay off this public repository.

## Where the files are, and why they are not in git

This repository is public. Two licenses block the binaries:

- SMPL-X is licensed per person from [smpl-x.is.tue.mpg.de](https://smpl-x.is.tue.mpg.de). The NPZ and meshes exported from it (including `smplx_thin.glb` and `smplx_body.glb`) are not redistributed.
- 4D-Dress subject 00127 is research data. The photos, the reconstructed OBJs, and the GLBs baked from them stay on the machine that downloaded them.

Local map, from the Dressme checkout on this PC:

| What | Path |
|---|---|
| Viewer | `avatar_studio/web/viewer/` |
| Worn GLBs | `avatar_studio/web/garments/shirt.glb`, `shorts.glb`, `vest.glb` |
| Reconstruction inputs and OBJs | `avatar_studio/web/garments/saved/kaggle/` |
| Pipeline scripts | `ai/remu/` and `ai/smplx_export.py`, `ai/skin_garments.py`, `ai/skin_textured.py`, `ai/apply_shirt_photo.py` |
| WSL ReMu | `~/remu/ReMu` |
| Weights | `D:\remu-weights` and `~/remu/ReMu/checkpoints/sith/recon_model.pth` |
| SMPL-X NPZ | `~/remu/ReMu/body_models/smplx/SMPLX_{MALE,FEMALE,NEUTRAL}.npz` |

`manifest.json` next to this file is the machine-readable copy of the viewer settings and the garment list. `POST /m09/render` returns it when mocks are off (`USE_MOCKS=false`). It does not return a rendered image.

## Resume checklist

1. Start the viewer from `avatar_studio/web` and open `viewer/index.html?mesh=/smplx_thin.glb&v=71`.
2. Click **Wear saved**. Pose chips should move the sleeves. The build sliders will not.
3. For a new garment at the same quality, use the Kaggle notebook at grid 384, then `kaggle_register.sh`, `bake_kaggle.sh`, `fit_baked.py`, and the two skin scripts. Do not run grid 512 on the laptop or on the T4.
4. Keep new weights on `D:`. Do not commit NPZ, GLB, OBJ, photos, or checkpoints.
