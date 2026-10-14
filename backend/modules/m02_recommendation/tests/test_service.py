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
