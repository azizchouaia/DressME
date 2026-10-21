"""M14 tests: a tiny M7 catalogue with a fake encoder, temporary data and logs (no model, no network)."""

import numpy as np
import pytest

from modules.m07_local_catalogue import events as m7_events
from modules.m07_local_catalogue import memory as m7_memory
from modules.m07_local_catalogue import service as m7_service
from modules.m07_local_catalogue.agent import LocalShopAgent
from modules.m07_local_catalogue.pipeline.catalogue import Catalogue
from modules.m07_local_catalogue.tests.test_search import FakeEncoder, product
from modules.m14_stylist_mode import paths
from modules.m14_stylist_mode.dashboard import data as dashboard_data

EN = {"sneakers": "sneakers", "shirt": "shirt", "sandals": "sandals", "dress": "dress", "suit": "suit"}


def row(pid, shop, name, sub, cat, color, price, city, gender=""):
    return {
        **product(pid, name, sub, cat, color, price, city, city, name),
        "shop_name": shop,
        "gender": gender,
    }


ROWS = [
    row("a1", "Manuella", "Baskets blanches femme", "sneakers", "shoes", "white", 75, "Tunis", "women"),
    row("a2", "Manuella", "Baskets noires", "sneakers", "shoes", "black", 95, "Tunis", "women"),
    row("a3", "Manuella", "Sandales noires", "sandals", "shoes", "black", 89, "Tunis", "women"),
    row("a4", "Manuella", "Robe rouge", "dress", "dress", "red", 120, "Tunis", "women"),
    row("b1", "Cravate", "Chemise blanche homme", "shirt", "top", "white", 70, "Tunis", "men"),
    row("b2", "Cravate", "Costume bleu marine", "suit", "dress", "navy", 290, "Tunis", "men"),
    row("c1", "Joliesse", "Robe noire", "dress", "dress", "black", 99, "Sousse", "women"),
    row("c2", "Joliesse", "Baskets blanches", "sneakers", "shoes", "white", 60, "Sousse", "women"),
]


@pytest.fixture
def m7_agent(tmp_path):
    enc = FakeEncoder()
    emb = enc.encode_texts([f"a photo of {r['color']} {EN[r['subcategory']]}" for r in ROWS])
    return LocalShopAgent(
        catalogue=Catalogue.from_records(ROWS, np.asarray(emb)),
        encoder=enc,
        memory=m7_memory.AgentMemory(tmp_path / "m7_memory"),
    )


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch, m7_agent):
    """Temporary M14 data, temporary M7 + simulated logs, the tiny catalogue behind M7's service."""
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path / "m14")
    real_log, sim_log = tmp_path / "m07_events.jsonl", tmp_path / "simulated.jsonl"
    monkeypatch.setattr(m7_events, "log_path", lambda: real_log)
    monkeypatch.setattr(paths, "SIMULATED_LOG", sim_log)
    monkeypatch.setattr(dashboard_data, "SIMULATED_LOG", sim_log)
    monkeypatch.setattr(m7_service, "knowledge_base_ready", lambda: True)
    monkeypatch.setattr(m7_service, "_agent", m7_agent)
    monkeypatch.setattr(m7_service, "_memory", m7_agent.memory)
    return {"real_log": real_log, "sim_log": sim_log}
