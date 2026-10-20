"""Multilingual captions, QR code on the card, ambassador leaderboard."""

import io

import pytest

from modules.m10_share_cards.agent import ShareAgent
from modules.m10_share_cards.pipeline import caption, metrics


def test_captions_in_three_languages():
    assert caption.caption("outfit", ["jebba"], None, [], "fr").startswith("Mon look du jour : jebba")
    assert caption.caption("outfit", ["jebba"], None, [], "tn").startswith("El lebsa mte3 el youm : jebba")
    assert caption.caption("outfit", ["jebba"], None, [], "xx").startswith("Today's look: jebba")


async def test_qr_code_is_drawn():
    pytest.importorskip("qrcode")
    from PIL import Image

    agent = ShareAgent()
    base = {
        "user_id": "u",
        "kind": "outfit",
        "items": [{"item_id": "i", "category": "top"}],
        "format": "square",
    }
    plain = await agent(base)
    with_qr = await agent({**base, "qr": True})
    a = Image.open(io.BytesIO(agent.store.get_png(plain["card_id"]))).convert("L")
    b = Image.open(io.BytesIO(agent.store.get_png(with_qr["card_id"]))).convert("L")
    corner = (1080 - 72 - 182, 1080 - 150 - 182, 1080 - 86, 1080 - 164)  # inside the QR box
    hist = lambda img: img.crop(corner).histogram()  # noqa: E731
    white, dark = lambda h: sum(h[240:]), lambda h: sum(h[:60])  # noqa: E731
    assert white(hist(b)) > 2000 and dark(hist(b)) > 2000  # black modules on a white box
    assert white(hist(b)) > white(hist(a)) + 1000  # the white QR box is new
    assert "qr" in with_qr["channel_links"] and "QR code" in with_qr["pipeline"][-4]["detail"]


def test_ambassadors_tiers():
    cards = [{"user_id": "omar", "short_code": "A"}, {"user_id": "sarra", "short_code": "B"}]
    opens = [{"short_code": "A"}] * 8 + [{"short_code": "B"}]
    signups = [{"short_code": "A", "new_user_id": f"n{i}"} for i in range(6)]
    rows = metrics.ambassadors(cards, opens, signups)
    assert rows[0]["user_id"] == "omar" and rows[0]["tier"] == "Style influencer" and rows[0]["points"] == 300
    assert rows[0]["to_next_tier"] == 14 and rows[1]["tier"] is None and rows[1]["to_next_tier"] == 1
