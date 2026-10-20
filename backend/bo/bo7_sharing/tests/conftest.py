import importlib.util

import pytest

# The BO7 tests need the extra packages of the M10 module (Pillow, numpy, scikit-learn, scipy).
_DEPS = ("PIL", "numpy", "sklearn", "scipy")
if any(importlib.util.find_spec(d) is None for d in _DEPS):
    collect_ignore_glob = ["test_*.py"]


@pytest.fixture(autouse=True)
def _plain_demo_wardrobe(monkeypatch):
    """API tests use the fixture wardrobe, not the photos of bo/bo7_sharing/demo_wardrobe/."""
    from modules.m15_challenges.singleton import challenges_agent
    from modules.m15_challenges.wardrobe import MockWardrobe

    monkeypatch.setattr(challenges_agent, "wardrobe", MockWardrobe())
