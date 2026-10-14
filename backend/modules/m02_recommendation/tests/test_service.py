"""End-to-end with the real pretrained models + demo wardrobe. Skipped when the model files are not pulled."""

import pytest

pytest.importorskip("torch")
pytest.importorskip("transformers")

from modules.m02_recommendation.contract import OutfitsResponse  # noqa: E402
from modules.m02_recommendation.engine import artifacts  # noqa: E402

pytestmark = pytest.mark.skipif(
    not (artifacts.CP_MODEL.exists() and artifacts.CIR_MODEL.exists() and artifacts.WARDROBE_EMB.exists()),
    reason="M2 model files not present (ml/models/m02)",
)

CTX = {"occasion": "work", "mood": "classy", "weather": {"temp_c": 9, "condition": "rain"}}


def test_recommend_real_models():
    from modules.m02_recommendation import service

    out = OutfitsResponse.model_validate(
        service.recommend({"user_id": "demo_f", "payload": {"context": CTX}})
    )
    assert out.mocked is False and len(out.result.outfits) == 3
    for o in out.result.outfits:
        assert 0 <= o.scores.compatibility <= 1
        assert "outerwear" in o.slots  # 9°C and rain


def test_complete_and_swap_real_models():
    from modules.m02_recommendation import service

    first = service.recommend({"user_id": "demo_m", "payload": {"context": CTX, "options": {"n": 1}}})
    outfit = first["result"]["outfits"][0]
    pin = outfit["slots"]["bottom"]
    done = service.complete({"user_id": "demo_m", "payload": {"context": CTX, "pinned_item_ids": [pin]}})
    assert all(pin in o["items"] for o in done["result"]["outfits"])
    sw = service.swap(
        {"user_id": "demo_m", "payload": {"context": CTX, "item_ids": outfit["items"], "slot": "shoes"}}
    )
    for o in sw["result"]["outfits"]:
        assert o["slots"]["shoes"] != outfit["slots"]["shoes"]
        assert o["slots"]["bottom"] == outfit["slots"]["bottom"]


def test_m2_reads_wear_log_and_status_from_m3(tmp_path, monkeypatch):
    from modules.m02_recommendation import service
    from modules.m03_wear_log import service as m03

    monkeypatch.setenv("M03_USE_MOCK", "false")
    monkeypatch.setenv("M03_DATABASE_URL", f"sqlite:///{(tmp_path / 'm03.sqlite').as_posix()}")
    req = {"user_id": "demo_f", "payload": {"context": CTX, "options": {"n": 1}}}
    first = service.recommend(req)["result"]
    assert first["wear_log_source"] == "m03"  # demo history imported into M3
    best = first["outfits"][0]
    # wear today's best outfit, and put another piece of it in the laundry
    m03.worn({"user_id": "demo_f", "payload": {"item_ids": best["items"]}})
    shoes = best["slots"]["shoes"]
    m03.status({"user_id": "demo_f", "payload": {"item_ids": [shoes], "status": "laundry"}})
    after = service.recommend({**req, "payload": {**req["payload"], "options": {"n": 3}}})["result"]
    for o in after["outfits"]:
        assert shoes not in o["items"]
        assert sorted(o["items"]) != sorted(best["items"])
