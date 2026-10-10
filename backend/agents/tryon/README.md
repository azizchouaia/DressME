# TryOnAgent — owner: M5

Render an outfit on the user's faceless 3D avatar built from body measurements.

## Contract
See `contract.py`. Example input: `tests/fixtures/input.json`.

## Pipeline steps
- `pipeline/body.py` — Fit SMPL-X shape parameters from measurements; export avatar GLB.
- `pipeline/garments.py` — Pick template mesh per category and apply the cutout texture.
- `pipeline/render.py` — Assemble avatar + garments into one GLB + preview PNG.
- `pipeline/fallback_2d.py` — 2D diffusion try-on (IDM-VTON / OOTDiffusion) when 3D is not available.

## Run tests
```bash
cd backend && pytest agents/tryon
```

## Status
- [ ] baseline working end-to-end with mocks
- [ ] first real model
- [ ] evaluated (metrics in `ml/notebooks/tryon/`)
