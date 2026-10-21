import importlib.util
import os

# tests keep the agents' memory in RAM (same SQLite code, nothing written to disk)
os.environ.setdefault("BO7_MEMORY_PATH", ":memory:")
os.environ.setdefault("BO7_SHARE_MEMORY_PATH", ":memory:")


# Only test_mock.py runs without the extra packages of modules/m10_share_cards/requirements.txt.
_DEPS = ("PIL", "numpy", "sklearn")
if any(importlib.util.find_spec(d) is None for d in _DEPS):
    collect_ignore_glob = ["test_[!m]*.py"]
