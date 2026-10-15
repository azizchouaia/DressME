import pytest

from modules.m07_local_catalogue import events


@pytest.fixture(autouse=True)
def event_log(tmp_path, monkeypatch):
    """Tests never write to the real search log (ml/data/logs/): each one gets its own file."""
    path = tmp_path / "m07_events.jsonl"
    monkeypatch.setattr(events, "log_path", lambda: path)
    return path
