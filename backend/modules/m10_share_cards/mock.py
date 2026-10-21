"""Week-1 mock of M10: fixed data in the agreed shape. service.py now implements it for real."""

SAMPLE = {
    "card_id": "card_mock",
    "short_code": "Ab3dE9x",
    "image_url": "/m10/cards/card_mock/image",
    "share_url": "https://dressme.tn/s/Ab3dE9x",
    "width": 1080,
    "height": 1920,
    "caption": "Today's look: linen shirt, beige chinos + brown loafers #MadeWithDressMe",
    "alt_text": "DressMe outfit card: linen shirt (top), beige chinos (bottom), loafers (shoes).",
    "background_hex": "#F6EAEA",
    "caption_source": "template",
    "channel_links": {"whatsapp": "https://wa.me/?text=...", "copy": "https://dressme.tn/s/Ab3dE9x?ch=copy"},
    "pipeline": [],
}


def card(req: dict) -> dict:
    return {"result": SAMPLE, "mocked": True}
