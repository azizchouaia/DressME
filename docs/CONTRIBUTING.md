# Contributing

## Daily workflow
```bash
git checkout main && git pull --rebase origin main
git checkout -b feat/vision-segmentation
# ... work only in your folders ...
git add -A && git commit -m "vision: add rembg segmentation step"
git pull --rebase origin main
git push -u origin feat/vision-segmentation
# open a Pull Request on GitHub
```

## Commit messages
`<area>: <what>` — e.g. `stylist: add MMR diversity`, `mobile/wardrobe: item grid`.

## Working on a shared module
1. Week 1: write `contract.py` (agree it with the BOs that use you) and `mock.py` (fixed data in that shape).
   The router serves the mock while `USE_MOCKS=true`, so nobody waits for you.
2. Write the real logic in `service.py` with the SAME signatures; flip `USE_MOCKS=false` when it is ready.
3. Need something from another module? Call its API (or its mock). Never re-implement it; ask the owner to add it.
4. A module the assistant should call ships a `tool.py` (see `modules/m06_smartbuy/tool.py`): the
   orchestrator picks it up automatically.

## Working on your BO
Your own tasks (`backend/bo/<your bo>/README.md`) live in `backend/bo/<your bo>/` and
`mobile/lib/features/<your bo>/`. Build them on top of the modules' APIs.

## Data and models
Never commit them. Use DVC:
```bash
dvc add ml/data/<dataset>
git add ml/data/<dataset>.dvc && git commit -m "data: add <dataset> v1"
dvc push
```
