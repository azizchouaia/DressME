"""M5 test fixtures: M1 mocked (demo wardrobe), M5 in memory, fresh caches for every test."""

import pytest

from shared.config import settings


@pytest.fixture(autouse=True)
def _isolated_m05(tmp_path, monkeypatch):
    from modules.m01_wardrobe import mock as m01_mock
    from modules.m05_style_profile import repository, service, styles

    monkeypatch.setenv("M01_DATA_DIR", str(tmp_path / "m01"))
    monkeypatch.setenv("M01_STORAGE", "local")
    monkeypatch.delenv("M01_USE_MOCKS", raising=False)
    monkeypatch.delenv("M05_STORE", raising=False)
    monkeypatch.delenv("M05_MIN_ITEMS", raising=False)
    monkeypatch.setattr(settings, "use_mocks", True)

    def reset():
        m01_mock._reset()
        repository._reset()
        styles._reset()
        service._looks_cache.clear()
        service._locks.clear()

    reset()
    yield
    reset()


@pytest.fixture
def bandit_mode(cfg, monkeypatch):
    """ranking: bandit, the contextual bandit kept for a context-dependent taste (the default is rocchio)."""
    monkeypatch.setattr(cfg, "ranking", "bandit")


@pytest.fixture
def cfg(monkeypatch):
    """The cached M5 config; change values with monkeypatch.setattr(cfg..., ...) so they are restored."""
    from modules.m05_style_profile.config import get_config

    return get_config()
