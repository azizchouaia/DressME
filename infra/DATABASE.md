# DressMe database (PostgreSQL 16 + pgvector)

One database for the whole team, in Docker. Tables are created by one script.

## 1. Once
1. Install **Docker Desktop** and start it.
2. Copy the settings: `copy infra\.env.example infra\.env` (Windows) / `cp infra/.env.example infra/.env`
3. Python drivers: `cd backend` → `python -m pip install -r requirements.txt`

## 2. Start the database
```
docker compose -f infra/docker-compose.yml up -d postgres
```
Check: `docker ps` shows `pgvector/pgvector:pg16` on port 5432.

## 3. Create the tables
```
cd backend
python -m scripts.init_db
```
Creates: `users` (accounts) · `items` (M1 wardrobe, pgvector 512) · `m03_*` (wear log) · `m04_*` (calendar)
and the demo account `demo@dressme.tn / demo1234`. Safe to run again.

## 4. Run the API as usual
`python -m uvicorn api.main:app --reload --port 8000` reads `infra/.env` by itself.
`GET /auth/store` answers `postgres` when accounts are in the database.

## Which module is real
Set in `infra/.env`:

| Switch | Real needs |
|---|---|
| `M01_USE_MOCKS=false` | Postgres + `pip install -r modules/m01_wardrobe/requirements.txt` (torch, FashionCLIP, rembg; first photo downloads the models) |
| `M03_USE_MOCK=false` + `M03_DATABASE_URL` | Postgres |
| `M04_DATABASE_URL` (+ `M04_USE_MOCK=false`) | Postgres + the real M2 |
| `M02_USE_MOCK=false` | Racem's model files in `ml/models/m02/` |
| `M09_USE_MOCK=false` | Blender (`M09_BLENDER=C:/.../blender.exe`) |

No database running? The API still starts: accounts go to `ml/data/users/users.json`, modules keep their mocks.

## Reset
`docker compose -f infra/docker-compose.yml down -v` deletes the database (all accounts and pieces).
