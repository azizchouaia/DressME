from modules.m06_smartbuy import explainer as ex

REASONS = ["you already own 5 t-shirts", "creates 40 new outfits", "0.9 TND per new outfit"]


class FakeResp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass

    def json(self):
        return {"message": {"content": self.text}}


def fake_llm(monkeypatch, text):
    import httpx
    monkeypatch.setattr(httpx, "post", lambda *a, **k: FakeResp(text))


def test_llm_text_is_used_when_safe(monkeypatch):
    fake_llm(monkeypatch, "Think twice: you already own 5 t-shirts, even if it creates 40 new outfits.")
    text, src = ex.explain("think", "Black t-shirt", REASONS, 35, "en")
    assert src == "llm" and "5 t-shirts" in text


def test_invented_number_falls_back_to_template(monkeypatch):
    fake_llm(monkeypatch, "Think twice: you own 12 t-shirts.")
    text, src = ex.explain("think", "Black t-shirt", REASONS, 35, "en")
    assert src == "template" and text.startswith("Think twice:")


def test_contradicting_the_verdict_is_refused(monkeypatch):
    fake_llm(monkeypatch, "Skip it? No, go for it, you will love it.")
    assert ex.explain("skip", "Black t-shirt", REASONS, 35, "en")[1] == "template"


def test_ollama_off_gives_template(monkeypatch):
    import httpx

    def boom(*a, **k):
        raise httpx.ConnectError("off")
    monkeypatch.setattr(httpx, "post", boom)
    assert ex.explain("buy", "Navy blazer", REASONS, 120, "fr")[1] == "template"
