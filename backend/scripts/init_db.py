"""Create every DressMe table in PostgreSQL (safe to run again: CREATE ... IF NOT EXISTS).

    docker compose -f ../infra/docker-compose.yml --env-file ../infra/.env up -d postgres
    python -m scripts.init_db

Reads infra/.env: DATABASE_URL (M1 + users), M03_DATABASE_URL, M04_DATABASE_URL.
Tables: users (auth) · items (M1, pgvector) · M3 wear log · M4 scheduler.
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_env() -> None:
    from dotenv import load_dotenv

    load_dotenv(ROOT.parent / "infra" / ".env")


def main() -> int:
    load_env()
    from sqlalchemy import create_engine, inspect, text

    from api.routes import auth
    from shared.config import settings

    url = os.environ.get("DATABASE_URL") or settings.database_url
    if not url.startswith("postgresql"):
        print("DATABASE_URL is not PostgreSQL. Copy infra/.env.example to infra/.env first.")
        return 1
    sync = auth.sync_url(url)
    print(f"database: {sync.split('@')[-1]}")
    eng = create_engine(sync, future=True)
    try:
        with eng.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.execute(text(auth.SCHEMA))
    except Exception as e:  # noqa: BLE001
        print(f"cannot reach PostgreSQL: {e}\nStart it: docker compose -f ../infra/docker-compose.yml --env-file ../infra/.env up -d postgres")
        return 1
    print("  ✓ extension vector, table users")

    from modules.m01_wardrobe import store as m1

    asyncio.run(m1.ensure_schema())
    print("  ✓ M1 items (pgvector)")

    for mod, var in (("m03_wear_log", "M03_DATABASE_URL"), ("m04_scheduler", "M04_DATABASE_URL")):
        if not os.environ.get(var, "").startswith("postgresql"):
            print(f"  - {mod}: {var} not set to Postgres -> it keeps its local SQLite file")
            continue
        storage = __import__(f"modules.{mod}.storage", fromlist=["session"])
        storage.session().close()  # creates its tables
        print(f"  ✓ {mod}")

    auth._pg_engine = None
    auth.get_user(auth.DEMO["email"])  # demo account
    print("  ✓ demo account demo@dressme.tn / demo1234")
    print("tables:", ", ".join(sorted(inspect(eng).get_table_names())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
