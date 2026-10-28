"""BO1/BO2 use the user's real M1 wardrobe (no Kaggle dataset): M1 image vector + M2 text vector = 1024."""

import asyncio

from shared import user_wardrobe, wardrobe


def test_m1_pieces_become_m2_items(monkeypatch):
    items = [
        {"item_id": "a", "category": "top", "subcategory": "linen shirt", "colors": [{"name": "navy", "hex": "#1F2A44", "share": 1}],
         "pattern": "solid", "material": "linen", "image_raw": "/m01/media/u/a.png", "image_cutout": None},
        {"item_id": "b", "category": "bottom", "subcategory": "chinos", "colors": [{"name": "beige", "hex": "#D8C3A5", "share": 1}],
         "pattern": "solid", "material": "cotton", "image_raw": "/m01/media/u/b.png", "image_cutout": None},
    ]

    async def fetch(user):
        return items, {"a": [0.1] * 512, "b": [0.2] * 512}

    monkeypatch.setattr(user_wardrobe, "_fetch", fetch)
    monkeypatch.setattr(user_wardrobe, "_text_vec", lambda text: tuple([0.5] * 512))
    monkeypatch.setattr("modules.m01_wardrobe.config.use_mocks", lambda default: False)
    out = user_wardrobe.m1_garments("usr_real")
    assert [g["item_id"] for g in out] == ["a", "b"]
    assert len(out[0]["embedding"]) == 1024 and out[0]["name"] == "navy linen linen shirt"
    assert user_wardrobe.m1_garments("demo_f") == []

    c = asyncio.run(wardrobe.catalog("usr_real"))
    assert c["source"] == "my wardrobe (M1)" and {i["id"] for i in c["items"]} == {"a", "b"}

    from modules.m02_recommendation import service
    own = service._m1_items("usr_real")
    assert len(own) == 2 and len(own[0].embedding) == 1024


def test_no_m1_falls_back(monkeypatch):
    monkeypatch.setattr("modules.m01_wardrobe.config.use_mocks", lambda default: True)
    assert user_wardrobe.m1_garments("usr_real") == []
