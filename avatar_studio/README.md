# BO9 · Avatar 3D

Mobile body creator for DressMe. The person you see is an official SMPL-X body. Photos are used to choose that body and its colors. The photo mesh itself is not the body you dress later.

Branch: `feat/bo9-avatar-3d`

## What you can do

- **Build.** One slider runs from thin to heavy, for a female or a male body. Height stays about 1.70 m. The other sliders still change the body you picked.
- **Body details.** One icon under Build opens Whole body, Upper body, Lower body, and Limbs. Those controls are the shape changes this SMPL-X mesh can actually make (chest, waist, hips, seat, thighs, arms, and so on). Bust size changes volume only.
- **Avatar.** A second icon is where you pick Female, Male, or Auto, and where you add photos. Auto uses the photos to guess the gender. Several photos are better than one: front or three-quarter is required, and side and back help.
- **Move.** Pose presets and the drag-to-pose work stay in the page, but nothing in the screen opens them yet.

The body stays in the middle of the screen. The Build bar sits above it and does not cover the head or the feet.

## How it is built

| Piece | Where | Role |
| --- | --- | --- |
| Viewer | `avatar_studio/web/viewer/` | Three.js page. Build, body sliders, and photos. |
| Flutter shell | `avatar_studio/lib/` | Full-screen frame around that page. |
| Body export | `ai/smplx_export.py` | Writes the thin, average, and heavy GLBs from official SMPL-X. |
| Photo server | `ai/triposr_server.py` | Local photo to mesh, plus skin and hair color. |
| Scan prepare | `ai/prepare_body.py` | Scales a raw scan before it is fitted. |

Build blends two shape differences (thin and heavy) on top of the average body of the chosen sex. The other sliders are mesh morphs on that same body, plus a few joint rotations (shoulder slope, pelvic tilt). They are not a second person model.

Starter bodies use only the first three SMPL-X shape values:

- thin: `-1.2, -2.0, 0.6`
- average: `0`
- heavy: `1.4, 2.2, -0.4`

## Run the viewer

From `avatar_studio`:

```bash
flutter run -d chrome --web-port 5290
```

Or open the page the Flutter app serves:

`http://127.0.0.1:5290/viewer/index.html?mesh=/smplx_body.glb`

The viewer loads Three.js from jsDelivr, so the 3D view needs a network connection.

## Models that are not in git

SMPL-X is official and non-commercial. Do not commit the NPZ files or any GLB made from them.

1. Download `SMPLX_NEUTRAL.npz`, `SMPLX_FEMALE.npz`, and `SMPLX_MALE.npz` from https://smpl-x.is.tue.mpg.de/
2. Put them in `ai/models/smplx/` (this folder is local only).
3. Generate the six starter bodies:

```bash
ai/vendor/TripoSR/.venv/Scripts/python.exe ai/smplx_export.py --presets avatar_studio/web/presets
```

The photo server is optional. It needs the local TripoSR checkout under `ai/vendor/TripoSR` and `ai/requirements-triposr.txt`. Generated user meshes go in `avatar_studio/web/users/` and are not committed. `*.glb` is already ignored by the DressME root `.gitignore`.

Clothing reconstruction (ReMu) is not part of this viewer. Helper scripts live in `ai/remu/` and run in WSL. They do not bind a garment to the Build slider.
