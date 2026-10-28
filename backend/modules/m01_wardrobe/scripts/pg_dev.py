"""Embedded PostgreSQL + pgvector for local dev without Docker (temporary, see run_real_local.ps1).

    python pg_dev.py start <pgdata>   -> starts (or reuses) the server, prints its URI on the last line
    python pg_dev.py stop  <pgdata>   -> stops it (the data stays in <pgdata>)

Runs in its own venv with `pgserver` (wheels exist for Python <= 3.12 on Windows).
"""

import sys
from pathlib import Path

import pgserver


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in ("start", "stop"):
        print(__doc__)
        return 2
    action, pgdata = sys.argv[1], Path(sys.argv[2]).resolve()
    pgdata.parent.mkdir(parents=True, exist_ok=True)
    if action == "start":
        srv = pgserver.get_server(pgdata, cleanup_mode=None)     # keeps running after this process exits
        srv.psql("SET client_min_messages = warning; CREATE EXTENSION IF NOT EXISTS vector;")
        print(srv.get_uri(), flush=True)
    else:
        srv = pgserver.get_server(pgdata, cleanup_mode="stop")
        srv.cleanup()
        print("stopped", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
