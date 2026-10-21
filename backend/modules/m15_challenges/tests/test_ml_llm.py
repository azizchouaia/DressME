"""ML (completion model) and LLM (RAG + prompt engineering coach) layers of M15."""

from modules.m10_share_cards.pipeline import llm
from modules.m15_challenges.agent import ChallengesAgent
from modules.m15_challenges.pipeline import coach, completion


class FakeShare:
    async def __call__(self, payload: dict) -> dict:
        return {"image_url": "/m10/cards/c/image", "share_url": "https://dressme.tn/s/c", "caption": "ok"}


def test_model_file_is_trained_and_good_enough():
    m = completion.model()
    assert m["features"] == ["feasibility", "valid_ratio", "streak", "progress", "social"]
    assert m["metrics"]["auc"] >= 0.8
    assert m["metrics"]["accuracy"] > m["metrics"]["baseline_accuracy"]


def test_probability_increases_with_good_behaviour():
    bad = completion.predict(completion.features(0.5, 1, 3, 0, 7, 0))
    good = completion.predict(completion.features(0.9, 3, 3, 3, 7, 4))
    assert 0 <= bad < good <= 1
    assert completion.risk(0.8) == "on_track" and completion.risk(0.5) == "at_risk"
    assert completion.risk(0.1) == "high_risk"


def test_coach_retrieves_matching_tip_and_falls_back(monkeypatch):
    monkeypatch.setattr(llm, "complete", lambda *a, **k: None)
    out = coach.advise(
        challenge="Traditional Friday",
        rule_types=["category_required"],
        day=1,
        valid=False,
        violations=["include at least 1 piece(s) from: traditional"],
        suggestion=["jebba"],
        probability=0.3,
        risk="high_risk",
        streak=0,
    )
    assert out["source"] == "template" and out["retrieved"][0]["id"].startswith("trad_")
    assert "Next: jebba" in out["message"] and "Tips (retrieved)" in out["prompt"]


def test_coach_uses_llm_when_available(monkeypatch):
    monkeypatch.setattr(llm, "complete", lambda s, u, **k: "Swap the jeans for the white jeans tomorrow!")
    out = coach.advise(
        challenge="7 days",
        rule_types=["no_repeat"],
        day=2,
        valid=False,
        violations=["straight jeans already worn on day 1"],
        suggestion=["white jeans"],
        probability=0.4,
        risk="at_risk",
        streak=0,
    )
    assert out["source"] == "llm" and "white jeans" in out["message"]


async def test_entry_result_exposes_input_code_output():
    agent = ChallengesAgent(share_agent=FakeShare())
    agent.join("amen", "ch_7x7")
    r = await agent.submit("amen", "ch_7x7", ["itm_t1", "itm_b1", "itm_s1"])
    stages = [s.stage for s in r.pipeline]
    methods = {s.method for s in r.pipeline}
    assert stages[0] == "input" and stages[-1] == "output"
    assert {"if/else", "ML", "LLM · RAG", "LLM · PE", "M10"} <= methods
    assert 0 <= r.progress.completion_probability <= 1 and r.progress.risk
    assert r.coach_message and r.coach_source == "template"


def test_llm_answer_is_cleaned():
    raw = '"Great start on day 2! Swap the red chechia for a grey one. Tomorrow: blouse + serwal. Extra."'
    out = llm.clean(raw, max_chars=320, max_sentences=3)
    assert not out.startswith('"') and not out.endswith('"')
    assert out.count(".") + out.count("!") == 3 and "Extra" not in out
    assert llm.clean("word " * 200, max_chars=50).endswith("word")
