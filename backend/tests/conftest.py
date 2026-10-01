import os
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_tmp = Path(tempfile.mkdtemp(prefix="smart-wardrobe-tests-"))
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp / 'test.db'}"
os.environ["STORAGE_LOCAL_ROOT"] = str(_tmp / "storage")
os.environ["SEED_DEMO_USER"] = "true"
os.environ["ENVIRONMENT"] = "test"

from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client() -> Iterator[TestClient]:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "ada@example.com", "password": "correct-horse", "display_name": "Ada"},
    )
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
