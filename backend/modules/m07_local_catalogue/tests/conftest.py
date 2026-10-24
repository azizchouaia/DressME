import pytest

from modules.m07_local_catalogue import events, llm, memory, service


@pytest.fixture(autouse=True)
def event_log(tmp_path, monkeypatch):
    """Tests never write to the real search log (ml/data/logs/): each one gets its own file."""
    path = tmp_path / "m07_events.jsonl"
    monkeypatch.setattr(events, "log_path", lambda: path)
    return path


@pytest.fixture(autouse=True)
def memory_dir(tmp_path, monkeypatch):
    """Tests never write to the real agent memory (ml/data/bo6/memory/): each one gets its own folder."""
    folder = tmp_path / "memory"
    monkeypatch.setattr(memory, "default_folder", lambda: folder)
    monkeypatch.setattr(service, "_memory", None)
    return folder


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    """Tests never call Ollama: the LLM is off unless a test installs a fake one (test_llm.py)."""
    monkeypatch.setattr(llm, "_llm", llm.LLM({"enabled": False, "model": "off", "url": "http://off"}))


@pytest.fixture(autouse=True)
def fresh_catalogue(monkeypatch):
    """The test catalogues are dated 2026-10-14: never "prices to check" because of today's date."""
    from modules.m07_local_catalogue.paths import CONFIG as M7_CONFIG

    monkeypatch.setitem(M7_CONFIG, "stale_after_days", 10**6)


@pytest.fixture(autouse=True)
def m14_and_tryon_dirs(tmp_path, monkeypatch):
    """Loyalty codes come from a temporary M14 folder; 3D models go to a temporary cache."""
    from modules.m07_local_catalogue.paths import CONFIG as M7_CONFIG
    from modules.m14_stylist_mode import paths as m14_paths

    monkeypatch.setattr(m14_paths, "data_dir", lambda: tmp_path / "m14")
    monkeypatch.setitem(M7_CONFIG, "tryon", {**M7_CONFIG["tryon"], "dir": str(tmp_path / "tryon")})
