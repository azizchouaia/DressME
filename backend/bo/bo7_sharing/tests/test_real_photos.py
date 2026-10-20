"""Real garment photos in the demo wardrobe (stand-in for M1): cutout, K-means colours, used by cards."""

import base64
import io

import pytest

pytest.importorskip("scipy")
from PIL import Image, ImageDraw  # noqa: E402

from bo.bo7_sharing.demo import cutout  # noqa: E402
from modules.m15_challenges.agent import ChallengesAgent  # noqa: E402
from modules.m15_challenges.wardrobe import MockWardrobe  # noqa: E402


def photo(bg=(214, 196, 170), shirt=(190, 35, 45)) -> bytes:
    """A red t-shirt lying on a beige bed sheet, with a little noise like a phone photo."""
    img = Image.new("RGB", (600, 600), bg)
    ImageDraw.Draw(img).polygon(
        [
            (150, 160),
            (250, 100),
            (350, 100),
            (450, 160),
            (410, 240),
            (380, 220),
            (380, 520),
            (220, 520),
            (220, 220),
            (190, 240),
        ],
        fill=shirt,
    )
    img = Image.eval(img, lambda v: v)  # copy
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_cutout_removes_background_and_finds_colour():
    res = cutout.run(photo())
    out = Image.open(io.BytesIO(res["png"]))
    assert out.mode == "RGBA" and out.width < 600  # cropped to the garment
    a = out.split()[-1]
    assert a.getpixel((2, out.height - 2)) < 50  # corner next to the sleeve is transparent
    assert a.getpixel((out.width // 2, out.height // 2)) > 200  # body is opaque
    assert res["colors"][0]["name"] == "red" and res["colors"][0]["share"] > 0.9
    assert {m for m, _, _ in res["steps"]} >= {"ML", "if/else"}


async def test_added_photo_is_used_by_rules_and_card(tmp_path):
    w = MockWardrobe(photos_dir=tmp_path)
    res = cutout.run(photo())
    w.save_photo(
        "itm_red", res["png"], {"category": "top", "subcategory": "red t-shirt", "colors": res["colors"]}
    )
    w.save_photo("itm_b1", res["png"])  # photo for an existing demo item
    items = {g.item_id: g for g in w.items("u")}
    assert items["itm_red"].image_cutout and items["itm_b1"].image_cutout
    assert items["itm_red"].colors[0].name == "red"

    seen = {}

    class Share:
        async def __call__(self, payload):
            seen.update(payload)
            return {"image_url": "/x", "share_url": "https://dressme.tn/s/x", "caption": "ok"}

    agent = ChallengesAgent(wardrobe=w, share_agent=Share())
    agent.join("u", "ch_7x7")
    r = await agent.submit("u", "ch_7x7", ["itm_red", "itm_b1", "itm_s1"])
    assert r.valid
    images = {i["item_id"]: i["image"] for i in seen["items"]}
    assert images["itm_red"].endswith("itm_red.png") and images["itm_s1"] is None

    assert w.delete("itm_red") and "itm_red" not in {g.item_id for g in w.items("u")}


def test_demo_upload_route(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from api.main import app
    from modules.m15_challenges.singleton import challenges_agent

    monkeypatch.setattr(challenges_agent, "wardrobe", MockWardrobe(photos_dir=tmp_path))
    c = TestClient(app)
    uri = "data:image/jpeg;base64," + base64.b64encode(photo()).decode()
    r = c.post("/bo7/demo/wardrobe/items", json={"image": uri, "category": "top", "name": "Red tee"})
    assert r.status_code == 200, r.text
    item = r.json()["item_id"]
    ward = {g["item_id"]: g for g in c.get("/bo7/demo/wardrobe").json()}
    assert ward[item]["photo_url"] and ward[item]["color"] == "red"
    assert c.get(ward[item]["photo_url"]).headers["content-type"] == "image/png"
    card = c.post(
        "/m10/cards",
        json={
            "user_id": "u",
            "kind": "board",
            "items": [{"item_id": item, "category": "top", "image": ward[item]["image"]}],
        },
    ).json()
    assert c.get(card["image_url"]).status_code == 200
    assert c.delete(f"/bo7/demo/wardrobe/items/{item}").status_code == 204
    assert c.post("/bo7/demo/wardrobe/items", json={"image": uri}).status_code == 400  # category missing
