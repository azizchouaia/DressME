# ai/ · BO9 avatar

Local scripts for the 3D body. Nothing here is served to the phone by itself. The page that uses the results is `avatar_studio/`.

| File | What it does |
| --- | --- |
| `smplx_export.py` | Builds thin, average, and heavy SMPL-X bodies (female and male), about 1.70 m tall. |
| `triposr_server.py` | Local photo server. Several photos, front/side/back labels, skin and hair color. |
| `prepare_body.py` | Cleans a raw scan and scales it before fitting. |
| `requirements-triposr.txt` | Python packages for that photo server. |
| `shims/torchmcubes/` | Small stand-in so TripoSR can import on this machine. |
| `remu/` | Optional WSL helpers for garment reconstruction. Not used by the viewer. |

`models/smplx/` is where the official SMPL-X NPZ files go after you download them from https://smpl-x.is.tue.mpg.de/. Those files stay on your machine.

`vendor/TripoSR/` is the local TripoSR checkout and its virtualenv. It is not part of this branch.

See `avatar_studio/README.md` for how to run the creator and what the Build slider does.
