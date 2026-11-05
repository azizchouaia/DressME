# Clothes pipeline and studio avatars

This is what another machine needs after pulling this branch. The studio page, the body meshes, the hair, the catalog clothes, and the saved avatars are already in the repository. The Kaggle key and the SMPL-X weight files are not, and must not be committed.

## Already in this repository

| Piece | Path |
| --- | --- |
| Studio page | `avatar_studio/web/studio` |
| Viewer | `avatar_studio/web/viewer` |
| Body meshes the viewer loads | `avatar_studio/web/smplx_thin.glb`, `smplx_body.glb`, `avatar_ready.glb` |
| Hairstyles (CC0) | `avatar_studio/web/hair` |
| Catalog clothes | `avatar_studio/web/garments` |
| Saved avatars and their outfits | `avatar_studio/web/avatars` |
| Pipeline code | `ai/remu/garment_pipeline.py` |
| Kaggle notebook | `ai/remu/kaggle_outfit` |
| Python libraries | `ai/requirements-studio.txt` |

`ai/vendor/` is git-ignored. It is a local checkout and a virtualenv, not something the next machine gets from git.

## Python

Use Python 3.12. From the repository root:

```bash
py -3 -m venv ai/.venv
ai\.venv\Scripts\python.exe -m pip install --upgrade pip
ai\.venv\Scripts\python.exe -m pip install -r ai/requirements-studio.txt
```

On macOS or Linux, the interpreter is `ai/.venv/bin/python`.

The first build does this install itself when `ai/vendor/TripoSR/.venv` is absent. Torch is unpinned on purpose: pip then selects a wheel that matches the machine. A CUDA wheel is the right one when the computer has an NVIDIA GPU. The download is large.

Check the environment with:

```bash
ai\.venv\Scripts\python.exe -c "import kaggle,six,torch,trimesh,smplx; from transformers import VitPoseForPoseEstimation; print('ready', torch.__version__)"
```

## Kaggle API key

Reconstruction runs on a Kaggle Tesla T4 and takes about 20 minutes. Create the key on the machine that runs the pipeline. Do not put it in git, in `.env`, or in the repository.

1. Sign in at [kaggle.com](https://www.kaggle.com).
2. Open [kaggle.com/settings/api](https://www.kaggle.com/settings/api).
3. Under API, generate a new token.

Put that token in one of these places.

**Option A. Environment variable.** Set it in the same terminal that starts the studio, before the build.

Windows:

```bat
set KAGGLE_API_TOKEN=paste-the-token-here
```

macOS or Linux:

```bash
export KAGGLE_API_TOKEN=paste-the-token-here
```

**Option B. Token file.** One line, the token only, no quotes.

- Windows: `C:\Users\YOUR_NAME\.kaggle\access_token`
- macOS or Linux: `~/.kaggle/access_token`

Create the `.kaggle` folder if it does not exist.

**Option C. Legacy username and key.** Same folder, file name `kaggle.json`:

```json
{"username": "your-kaggle-username", "key": "your-legacy-key"}
```

The same two values can be environment variables named `KAGGLE_USERNAME` and `KAGGLE_KEY`.

Confirm the login without printing the token:

```bash
ai\.venv\Scripts\python.exe -m kaggle datasets list -m --csv
```

A table of your datasets means the key is in the right place.

### Which Kaggle account

The notebook and the private datasets belong to `nadhirmaamar`:

- Notebook: `nadhirmaamar/dressme-outfit-pipeline`
- Photos: `nadhirmaamar/dressme-garment-photos`
- SMPL-X body used on the GPU: `nadhirmaamar/dressme-smplx-body`

The token has to be allowed to update those. They are named in `ai/remu/garment_pipeline.py` (`DATASET_ID`, `KERNEL_ID`) and in `ai/remu/kaggle_outfit/kernel-metadata.json`. A different Kaggle account needs those three ids changed to its own username, a new private GPU notebook, and its own copy of the SMPL-X dataset attached to that notebook.

## SMPL-X weights

The official SMPL-X `.npz` files are under a non-commercial licence and are not in this repository. The GPU notebook reads them from the private dataset `nadhirmaamar/dressme-smplx-body`. Do not commit `SMPLX_MALE.npz`, `SMPLX_FEMALE.npz`, `SMPLX_NEUTRAL.npz`, or a `body_models/` download.

The viewer does not need those files. It uses the GLB meshes already stored under `avatar_studio/web/`.

## Run the studio

```bash
ai\.venv\Scripts\python.exe ai\remu\studio_server.py
```

Open [http://127.0.0.1:8893](http://127.0.0.1:8893).

Create a person, add a front photo and a back photo, then build the avatar. The page stays on "Reconstructing in 3D" for about 20 minutes while Kaggle runs. When that finishes, the computer downloads the mesh and fits the shirt and pants. Later outfits for the same person reuse the avatar and only rebuild the clothes.

A phone does not run this pipeline. It only opens the studio that this computer is serving.
