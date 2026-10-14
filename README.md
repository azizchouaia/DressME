# DressMe — AI digital wardrobe (multi-agent mobile app)

ESPRIT 2026 · Team of 6

DressMe digitises the user's clothes and uses a team of AI agents to recommend outfits,
judge new purchases, find local Tunisian pieces and show looks on a faceless 3D avatar.

## Repository layout

The work is split by **business objective (BO)** in two parts:
- **Shared modules** (`backend/modules/m01…m18`): built ONCE by one owner, exposed as an API, called by everyone.
- **Own tasks** (`backend/bo/bo1…bo9` + `mobile/lib/features/bo1…bo9`): screens and features specific to one BO.

| Folder | What | Owner |
|---|---|---|
| `backend/modules/` | 18 shared modules, see [modules/README.md](backend/modules/README.md) | one BO each |
| `backend/bo/` | own tasks per BO (README = task list + modules called) | that BO |
| `backend/orchestrator/` | assistant agent, calls every module that ships a `tool.py` | BO8 |
| `backend/api/` | gateway: includes every `modules/*/router.py` automatically | M6 owner / lead |
| `backend/shared/` | schemas (Item, Outfit, Event), config, storage | review required |
| `mobile/lib/features/boX_*` | Flutter screens of each BO | that BO |
| `ml/`, `infra/`, `docs/` | data (DVC), Docker, documentation | everyone |

Build order: week 1 M1 + M2 (+ schema and mocks for all) · week 2 M3, M5, M6 · week 3 M4, M7, M8, M9, M10 ·
week 4 M11–M18 · week 5+ own tasks of every BO, integration, demo.

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
2. Work **only inside your own folders** (your modules + your `bo/` and `features/` folder) (see table and `.github/CODEOWNERS`).
3. `backend/shared/schemas/` is the contract between agents: change it only via a PR reviewed by M6.
4. `git pull --rebase origin main` before pushing; open a PR; one approval to merge.
5. Run `pre-commit install` once; formatting is automatic (ruff for Python, dart format for Flutter).
6. Never commit data, weights, `.env` or secrets. Data/models go through DVC.

See `docs/CONTRIBUTING.md` for details and `docs/architecture.md` for the pipeline.
