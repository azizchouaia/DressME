"""M1 test fixtures. Slow tests (real models) run only with M01_RUN_SLOW=1."""

import os

import pytest

from shared.config import settings


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: loads the real models (rembg, FashionCLIP); set M01_RUN_SLOW=1")


def pytest_collection_modifyitems(config, items):
    if os.environ.get("M01_RUN_SLOW") == "1":
        return
    skip = pytest.mark.skip(reason="slow: set M01_RUN_SLOW=1 to run")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _isolated_m01(tmp_path, monkeypatch):
    """Fresh demo wardrobe, images written to a temp dir, mock mode on."""
    from modules.m01_wardrobe import mock

    monkeypatch.setenv("M01_DATA_DIR", str(tmp_path / "m01"))
    monkeypatch.setenv("M01_STORAGE", "local")
    monkeypatch.delenv("M01_USE_MOCKS", raising=False)
    monkeypatch.setattr(settings, "use_mocks", True)
    mock._reset()
    yield
    mock._reset()
