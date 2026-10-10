# VisionAgent — owner: M1

Digitise a garment photo: remove background, classify type/colour/season, compute an embedding.

## Contract
See `contract.py`. Example input: `tests/fixtures/input.json`.

## Pipeline steps
- `pipeline/segment.py` — Background removal (rembg / SAM 2). Returns cutout image bytes.
- `pipeline/classify.py` — Category, subcategory, pattern, season, formality (fine-tuned ViT / FashionCLIP zero-shot).
- `pipeline/colors.py` — Dominant colours via K-means in LAB space + colour naming.
- `pipeline/embed.py` — FashionCLIP 512-d embedding of the cutout.

## Run tests
```bash
cd backend && pytest agents/vision
```

## Status
- [ ] baseline working end-to-end with mocks
- [ ] first real model
- [ ] evaluated (metrics in `ml/notebooks/vision/`)
