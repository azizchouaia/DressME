import base64
import io
import json
from pathlib import Path

import pytest

from modules.m10_share_cards.agent import ShareAgent
from modules.m10_share_cards.pipeline import caption, layout, links, metrics, palette
from shared.base_agent import AgentError

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "input.json").read_text())
AREA = (72, 330, 936, 1440)


# ---------- layout ----------
def test_layout_rows_follow_the_body():
    items = [{"item_id": i, "category": c} for i, c in [("s", "shoes"), ("b", "bottom"), ("t", "top")]]
    boxes = {b.item_id: b for b in layout.run(items, AREA)}
    assert boxes["t"].y < boxes["b"].y < boxes["s"].y


def test_layout_stays_inside_area_and_never_overlaps():
    items = [
        {"item_id": str(i), "category": c}
        for i, c in enumerate(["outerwear", "top", "bottom", "shoes", "accessory", "accessory"])
    ]
    boxes = layout.run(items, AREA)
    x, y, w, h = AREA
    for b in boxes:
        assert x <= b.x and b.x + b.w <= x + w + 1
        assert y <= b.y and b.y + b.h <= y + h + 1
    for a in boxes:
        for b in boxes:
            if a is not b:
                apart = a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y
                assert apart


def test_layout_outerwear_left_of_top():
    boxes = {
        b.item_id: b
        for b in layout.run(
            [{"item_id": "t", "category": "top"}, {"item_id": "o", "category": "outerwear"}], AREA
        )
    }
    assert boxes["o"].x < boxes["t"].x


def test_layout_empty():
    assert layout.run([], AREA) == []


# ---------- palette ----------
def test_light_clothes_get_dark_background_and_readable_text():
    p = palette.run(["#F1EFE9", "#FFFFFF"])
    assert palette.relative_luminance(p.background) < 0.2
    assert palette.contrast_ratio(p.background, p.text) >= 4.5


def test_dark_clothes_get_light_background():
    p = palette.run(["#1E1B22", "#4A4650"])
    assert palette.relative_luminance(p.background) > 0.7
    assert palette.contrast_ratio(p.background, p.text) >= 4.5


def test_palette_without_colours():
    assert palette.run([None]).background.startswith("#")


# ---------- links ----------
def test_short_codes_are_7_base62_chars_and_unique():
    codes = {links.short_code("u1", "o1") for _ in range(200)}
    assert len(codes) == 200
    assert all(len(c) == 7 and c.isalnum() for c in codes)
    assert links.share_url("https://dressme.tn/", "abc1234") == "https://dressme.tn/s/abc1234"


def test_short_code_is_deterministic_with_nonce():
    assert links.short_code("u", "s", "n") == links.short_code("u", "s", "n")


# ---------- caption ----------
def test_caption_and_alt_text():
    c = caption.caption("outfit", ["Linen shirt", "Chinos", "Loafers"], None, [])
    assert "Linen shirt, Chinos + Loafers" in c and caption.HASHTAG in c
    assert "Linen shirt (top)" in caption.alt_text("outfit", [("Linen shirt", "top")], "Look")


# ---------- metrics ----------
def test_k_factor():
    cards = [{"card_id": f"c{i}", "user_id": f"u{i % 2}", "short_code": f"k{i}"} for i in range(4)]
    opens = [{"short_code": "k0"}] * 6 + [{"short_code": "k1"}] * 2
    signups = [{"short_code": "k0", "new_user_id": "n1"}, {"short_code": "k1", "new_user_id": "n2"}]
    m = metrics.compute(cards, opens, signups)
    assert (m.cards, m.sharers, m.opens, m.signups) == (4, 2, 8, 2)
    assert m.ctr == 2.0 and m.conversion == 0.25 and m.invites_per_sharer == 2.0
    assert m.k_factor == pytest.approx(1.0)


def test_project_growth():
    assert metrics.project_growth(100, 0.5, 3) == [150, 175, 188]
    assert metrics.project_growth(10, 1.2, 2)[-1] > 10 * 2


# ---------- agent end-to-end ----------
async def test_agent_renders_png_and_tracks_referrals():
    pytest.importorskip("PIL")
    from PIL import Image

    agent = ShareAgent()
    out = await agent(FIXTURE)
    assert out["share_url"].endswith(out["short_code"])
    png = agent.store.get_png(out["card_id"])
    img = Image.open(io.BytesIO(png))
    assert img.size == (1080, 1920)

    agent.open_link(out["short_code"])
    agent.open_link(out["short_code"])
    agent.attribute_signup(out["short_code"], "usr_new")
    agent.attribute_signup(out["short_code"], "usr_new")  # counted once
    m = agent.metrics("usr_042")
    assert (m.cards, m.opens, m.signups) == (1, 2, 1)


async def test_agent_uses_real_cutout_when_given():
    pytest.importorskip("PIL")
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGBA", (200, 300), (200, 30, 60, 255)).save(buf, format="PNG")
    data_uri = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    agent = ShareAgent()
    out = await agent(
        {
            "user_id": "u",
            "kind": "board",
            "format": "square",
            "items": [{"item_id": "i", "category": "top", "image": data_uri}],
        }
    )
    img = Image.open(io.BytesIO(agent.store.get_png(out["card_id"]))).convert("RGB")
    assert img.size == (1080, 1080)
    assert (200, 30, 60) in {img.getpixel((x, 600)) for x in range(300, 800, 10)}


async def test_stats_only_card():
    pytest.importorskip("PIL")
    out = await ShareAgent()(
        {
            "user_id": "u",
            "kind": "recap",
            "title": "My month in outfits",
            "stats": [{"label": "outfits worn", "value": "23"}],
        }
    )
    assert "outfits worn: 23" in out["caption"]


async def test_empty_card_is_rejected():
    with pytest.raises(AgentError):
        await ShareAgent()({"user_id": "u"})


def test_unknown_code():
    with pytest.raises(AgentError):
        ShareAgent().open_link("nope000")
