"""ML (K-means colours) and LLM (RAG + prompt engineering) layers of M10."""

import base64
import io

import pytest

from modules.m10_share_cards.agent import ShareAgent
from modules.m10_share_cards.pipeline import caption_llm, llm
from modules.m10_share_cards.pipeline.rag import Doc, Retriever


def test_retriever_ranks_relevant_doc_first():
    r = Retriever(
        [
            Doc("a", "monthly recap numbers stats"),
            Doc("b", "trip lookbook travel packing"),
            Doc("c", "give-away donate sweater"),
        ]
    )
    assert r.search("my trip to Djerba, packing light")[0][0].id == "b"


def test_caption_prompt_contains_retrieved_guidelines_and_facts():
    prompt, docs = caption_llm.build_prompt("giveaway", ["Sage sweater"], [], "Giving away", "Size M", [])
    assert docs and docs[0]["id"] == "giveaway_kind"
    assert "Guidelines (retrieved)" in prompt and "Sage sweater" in prompt and "Example" in prompt


def test_caption_falls_back_to_template_without_llm(monkeypatch):
    monkeypatch.setattr(llm, "complete", lambda *a, **k: None)
    out = caption_llm.write("outfit", ["Linen shirt"], [], None, None, [])
    assert out["source"] == "template" and "#MadeWithDressMe" in out["caption"]


def test_caption_uses_llm_when_available(monkeypatch):
    monkeypatch.setattr(llm, "complete", lambda system, user, **k: "24°C, linen mood. #OOTD")
    out = caption_llm.write("outfit", ["Linen shirt"], [], None, "24°C", [])
    assert out == {**out, "source": "llm", "caption": "24°C, linen mood. #OOTD"}


def test_llm_not_available_by_default():
    assert llm.available() is False  # no key in the test environment → template path


def _two_colour_png() -> str:
    from PIL import Image

    img = Image.new("RGBA", (100, 100), (0, 0, 0, 0))  # transparent background (ignored)
    for x in range(10, 90):
        for y in range(10, 90):
            img.putpixel((x, y), (200, 30, 60, 255) if y < 70 else (20, 20, 20, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def test_kmeans_dominant_colour():
    pytest.importorskip("sklearn")
    from modules.m10_share_cards.pipeline import colors_ml
    from modules.m10_share_cards.pipeline.render import load_image

    cols = colors_ml.dominant_colors(load_image(_two_colour_png()), k=2)
    assert cols[0][0] == "#C81E3C" and cols[0][1] == pytest.approx(0.75, abs=0.02)


async def test_agent_pipeline_trace_has_every_layer():
    pytest.importorskip("PIL")
    out = await ShareAgent()(
        {
            "user_id": "u",
            "kind": "board",
            "items": [{"item_id": "i", "category": "top", "image": _two_colour_png()}],
        }
    )
    methods = [s["method"] for s in out["pipeline"]]
    assert methods[0] == "data" and methods[-1] == "data"
    assert {"ML", "if/else", "LLM · RAG", "LLM · PE"} <= set(methods)
    assert "learned from 1 cutout" in out["pipeline"][1]["detail"]
    assert out["retrieved"] and out["prompt"]
