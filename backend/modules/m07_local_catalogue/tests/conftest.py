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
