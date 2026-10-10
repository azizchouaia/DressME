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

## Adding a new agent
1. Copy `backend/agents/_template/` to `backend/agents/<name>/`.
2. Define `contract.py` (input/output) — reuse models from `backend/shared/schemas`.
3. Implement `agent.py` (`run()`), keep steps in `pipeline/`.
4. Register it in `backend/orchestrator/registry.py` (one line).
5. Add fixtures + tests in `tests/`.

## Data and models
Never commit them. Use DVC:
```bash
dvc add ml/data/tunisian_garments
git add ml/data/tunisian_garments.dvc && git commit -m "data: add tunisian garments v1"
dvc push
```
