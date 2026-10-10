# ML workspace

- `notebooks/<agent>/` — experiments of each owner (clear outputs before committing)
- `data/` — datasets, tracked with **DVC** (not git)
- `models/` — trained weights, tracked with **DVC**
- `scripts/` — reusable training / evaluation scripts

Log every experiment in MLflow: `mlflow ui` then open http://localhost:5000.
