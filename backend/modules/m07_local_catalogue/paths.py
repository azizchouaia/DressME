"""Where M7 keeps its data and weights. Data and models live under ml/ and are tracked with DVC, not git
(ml/README.md): the shop knowledge base in ml/data/shops/, FashionCLIP weights optionally in ml/models/.
"""

from pathlib import Path

import yaml

MODULE_DIR = Path(__file__).resolve().parent
REPO_ROOT = MODULE_DIR.parents[2]
CONFIG = yaml.safe_load((MODULE_DIR / "config.yaml").read_text(encoding="utf-8"))

DATA_DIR = REPO_ROOT / CONFIG["data_dir"]
RAW_CSV = DATA_DIR / "local_catalogue.csv"  # scraper output
CATALOGUE_CSV = DATA_DIR / CONFIG["catalogue_csv"]  # cleaned knowledge base
INDEX_DIR = DATA_DIR / CONFIG["index_dir"]  # FashionCLIP embeddings
IMAGES_DIR = DATA_DIR / "images"


def model_source() -> str:
    """Local copy in ml/models/ (DVC) when present, else the Hugging Face id (downloaded into its cache)."""
    local = REPO_ROOT / CONFIG["model_dir"]
    return str(local) if (local / "config.json").is_file() else CONFIG["embedding_model"]
