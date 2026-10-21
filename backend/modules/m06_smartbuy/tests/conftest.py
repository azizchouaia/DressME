import pytest


@pytest.fixture(autouse=True)
def no_local_llm(request, monkeypatch):
    """Tests stay fast and repeatable: the local LLM (Ollama) is off, except in test_explainer.py."""
    if request.module.__name__.endswith("test_explainer"):
        return
    from modules.m06_smartbuy import explainer
    from modules.m18_size_fit import text_fit
    monkeypatch.setattr(explainer, "llm", lambda *a, **k: None)
    monkeypatch.setattr(text_fit, "parse_llm", lambda *a, **k: None)
