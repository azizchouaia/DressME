"""Call another module of the SAME API in-process (no HTTP to ourselves).

Several modules called the gateway over HTTP (api_url = 127.0.0.1:8000) with a blocking client. Inside a
running request that blocks the event loop of the single dev server: the call waits for itself until the
timeout, then the module silently uses its mock. In-process calls go straight to the route, same contract.
"""

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def _client():
    from fastapi.testclient import TestClient

    from api.main import app

    return TestClient(app, raise_server_exceptions=True)


def post(path: str, body: dict, timeout: float | None = None) -> dict:
    r = _client().post(path, json=body)
    r.raise_for_status()
    return r.json()


def get(path: str, params: dict | None = None) -> dict:
    r = _client().get(path, params=params)
    r.raise_for_status()
    return r.json()
