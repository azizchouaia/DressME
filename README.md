# DressMe — AI digital wardrobe (multi-agent mobile app)

ESPRIT 2026 · Team of 6

DressMe digitises the user's clothes and uses a team of AI agents to recommend outfits,
judge new purchases, find local Tunisian pieces and show looks on a faceless 3D avatar.

## Repository layout

| Folder | What lives there | Owner |
|---|---|---|
| `mobile/` | Flutter app (one folder per feature) | each member owns their feature |
| `backend/api/` | FastAPI gateway, auth, routes | M6 |
| `backend/orchestrator/` | LangGraph orchestrator agent | M6 |
| `backend/agents/vision/` | Garment segmentation, classification, embeddings | M1 |
| `backend/agents/stylist/` | Outfit generation & compatibility | M2 |
| `backend/agents/profile/` | Style learning & wardrobe analytics | M3 |
| `backend/agents/smartbuy/` | Purchase compatibility score | M4 |
| `backend/agents/localshop/` | RAG over Tunisian shops | M4 |
| `backend/agents/tryon/` | Faceless 3D avatar try-on | M5 |
| `backend/shared/` | Schemas (data contract), base agent, DB, storage | M6 (review required) |
| `ml/` | Notebooks, datasets (DVC), model weights (DVC) | everyone |
| `infra/` | Docker Compose, env files | M6 |
| `docs/` | Architecture, decisions, reports | everyone |

## Quick start

```bash
cp infra/.env.example infra/.env
docker compose -f infra/docker-compose.yml up -d     # postgres, redis, minio
cd backend && python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn api.main:app --reload                        # http://localhost:8000/docs
```

Mobile:

```bash
cd mobile && flutter pub get && flutter run
```

## Team rules (read before your first commit)

1. **Never push to `main`.** One branch per task: `feat/<area>-<task>`, `fix/<area>-<bug>`.
2. Work **only inside your own folders** (see table and `.github/CODEOWNERS`).
3. `backend/shared/schemas/` is the contract between agents: change it only via a PR reviewed by M6.
4. `git pull --rebase origin main` before pushing; open a PR; one approval to merge.
5. Run `pre-commit install` once; formatting is automatic (ruff for Python, dart format for Flutter).
6. Never commit data, weights, `.env` or secrets. Data/models go through DVC.

See `docs/CONTRIBUTING.md` for details and `docs/architecture.md` for the pipeline.
