"""Where M14 keeps its data (ml/, never git) and its configuration."""

from pathlib import Path

import yaml

MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parents[2]
CONFIG = yaml.safe_load((MODULE_DIR / "config.yaml").read_text(encoding="utf-8"))

SIMULATED_LOG = REPO_ROOT / CONFIG["simulated_log"]


def data_dir() -> Path:
    """JSON collections of M14 (a function so tests can point it to a temporary folder)."""
    return REPO_ROOT / CONFIG["data_dir"]
