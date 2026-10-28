"""BO7 · share a 3D avatar look: BO9's viewer served by BO7, M9 asked for an image, M10 "tryon" card."""

import base64
import io

import pytest
from fastapi.testclient import TestClient

pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from api.main import app  # noqa: E402
from bo.bo7_sharing import avatar  # noqa: E402

client = TestClient(app)
PIECES = [
    {"item_id": "a", "category": "top", "label": "Linen shirt", "color_hex": "#E3CFAE"},
    {"item_id": "b", "category": "bottom", "label": "Chinos", "color_hex": "#D9C3A0"},
]


def _png_data_uri(color=(120, 110, 100, 255), size=(120, 300)) -> str:
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (60, 260), color), (30, 20))  # a figure on a transparent background
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def _card(**extra) -> Image.Image:
    r = client.post("/m10/cards", json={"user_id": "usr_av", "kind": "tryon", "items": PIECES, **extra})
    assert r.status_code == 200, r.text
    png = client.get(r.json()["image_url"])
    assert png.status_code == 200
    return Image.open(io.BytesIO(png.content)).convert("RGB")


def test_status_reports_viewer_bodies_and_m9_mock():
    s = client.get("/bo7/avatar/status").json()
    assert s["viewer_url"].startswith("/bo7/avatar/viewer/")
    assert isinstance(s["bodies"], list)
    assert s["m9"]["image"] is None and s["m9"]["mocked"] is True  # M9 is still BO9's mock


@pytest.mark.skipif(not (avatar.VIEWER / "index.html").exists(), reason="BO9 viewer not merged")
def test_viewer_is_served_with_the_snapshot_script_and_bo9_file_unchanged():
    html = client.get("/bo7/avatar/viewer/").text
    original = (avatar.VIEWER / "index.html").read_text(encoding="utf-8")
    assert "bo7-snapshot" in html and "preserveDrawingBuffer" in html
    assert "bo7-snapshot" not in original  # rule 4: BO9's file is not modified
    assert client.get("/bo7/avatar/viewer/scene.mjs").status_code == 200


def test_viewer_url_opens_a_body_when_bo9_generated_one(monkeypatch, tmp_path):
    monkeypatch.setattr(avatar, "ROOT", tmp_path)
    assert avatar.viewer_url([]) == "/bo7/avatar/viewer/"
    url = avatar.viewer_url(["female_average.glb", "male_thin.glb"])
    assert url.endswith("?mesh=/presets/female_average.glb")
    (tmp_path / "smplx_body.glb").write_bytes(b"glb")
    assert avatar.viewer_url([]).endswith("?mesh=/smplx_body.glb")


def test_files_cannot_leave_the_avatar_folder():
    assert client.get("/bo7/avatar/files/../../backend/api/main.py").status_code == 404
    assert client.get("/bo7/avatar/files/presets/nothing.glb").status_code == 404


def test_tryon_card_draws_the_avatar_left_and_the_pieces_right():
    with_avatar = _card(avatar_image=_png_data_uri())
    without = _card()  # no picture yet: faceless mannequin, the card still renders
    assert with_avatar.size == without.size == (1080, 1920)
    # the left half differs (avatar vs mannequin), the right column (pieces) is drawn in both
    left = (100, 500, 600, 1500)
    assert list(with_avatar.crop(left).getdata()) != list(without.crop(left).getdata())


def test_empty_capture_counts_as_no_avatar():
    blank = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
    buf = io.BytesIO()
    blank.save(buf, format="PNG")
    empty = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()
    a, b = _card(avatar_image=empty), _card()
    region = (100, 500, 600, 1500)
    assert list(a.crop(region).getdata()) == list(b.crop(region).getdata())  # both show the mannequin


def test_flutter_app_route_explains_how_to_build_when_missing(monkeypatch, tmp_path):
    from bo.bo7_sharing import app as flutter_app

    monkeypatch.setattr(flutter_app, "BUILD", tmp_path / "web")
    r = client.get("/bo7/app/")
    assert r.status_code == 404 and "flutter build web" in r.json()["detail"]
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "index.html").write_text("<html>app</html>")
    (tmp_path / "web" / "main.dart.js").write_text("// js")
    assert client.get("/bo7/app/").text == "<html>app</html>"
    assert client.get("/bo7/app/main.dart.js").text == "// js"
    assert client.get("/bo7/app/some/route").text == "<html>app</html>"  # the app's router handles it


def test_viewer_module_is_served_as_javascript():
    """Windows maps .mjs to text/plain; the browser would refuse BO9's module script."""
    r = client.get("/bo7/avatar/viewer/scene.mjs")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/javascript")


def _glb_with_texture(color=(200, 200, 200)) -> bytes:
    import json
    import struct

    buf = io.BytesIO()
    Image.new("RGBA", (8, 8), (*color, 255)).save(buf, format="PNG")
    png = buf.getvalue() + b"\0" * (-len(buf.getvalue()) % 4)
    gltf = {
        "asset": {"version": "2.0"},
        "buffers": [{"byteLength": len(png)}],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": len(buf.getvalue())}],
        "images": [{"bufferView": 0, "mimeType": "image/png"}],
        "textures": [{"source": 0}],
        "materials": [{"pbrMetallicRoughness": {"baseColorTexture": {"index": 0}}}],
    }
    js = json.dumps(gltf).encode()
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(png)
    return (
        struct.pack("<III", 0x46546C67, 2, total)
        + struct.pack("<II", len(js), 0x4E4F534A)
        + js
        + struct.pack("<II", len(png), 0x004E4942)
        + png
    )


def _texture_of(glb: bytes) -> Image.Image:
    import json
    import struct

    n = struct.unpack_from("<I", glb, 12)[0]
    gltf = json.loads(glb[20 : 20 + n])
    binary = glb[28 + n :]
    view = gltf["bufferViews"][gltf["images"][0]["bufferView"]]
    start = view["byteOffset"]
    return Image.open(io.BytesIO(binary[start : start + view["byteLength"]])).convert("RGB")


def test_garment_texture_takes_the_colour_of_the_picked_piece():
    out = avatar.recolor_glb(_glb_with_texture(), (176, 58, 46))  # a red top
    r, g, b = _texture_of(out).getpixel((4, 4))
    assert r > g + 40 and r > b + 40  # the shirt is now red
    assert avatar.recolor_glb(b"not a glb at all....", (1, 2, 3)) == b"not a glb at all...."


def test_garment_route_recolours_and_leaves_the_half_built_vest_out(monkeypatch, tmp_path):
    (tmp_path / "garments").mkdir()
    (tmp_path / "garments" / "shirt.glb").write_bytes(_glb_with_texture())
    monkeypatch.setattr(avatar, "ROOT", tmp_path)
    r = client.get("/bo7/avatar/garment/shirt.glb?topc=1F3A5F")
    assert r.status_code == 200 and r.headers["content-type"] == "model/gltf-binary"
    r_, g_, b_ = _texture_of(r.content).getpixel((4, 4))
    assert b_ > r_  # navy
    assert client.get("/bo7/avatar/garment/vest.glb").content == avatar.EMPTY_GLB
    assert client.get("/bo7/avatar/garment/hat.glb").status_code == 404


def test_shape_rules_follow_the_piece():
    from bo.bo7_sharing.avatar_dress import shape_for

    assert shape_for("shorts", "bottom", "grey and beige trousers") == "trousers"
    assert shape_for("shorts", "bottom", "white serwal") == "trousers"
    assert shape_for("shorts", "bottom", "red skirt") == "skirt"
    assert shape_for("shorts", "bottom", "grey shorts") == "shorts"
    assert shape_for("shirt", "top", "grey t-shirt") == "short_top"
    assert shape_for("shirt", "top", "black hoodie") == "long_top"
    assert shape_for("shirt", "dress", "navy dress") == "dress"
    assert shape_for("shirt", "traditional", "white embroidered jebba") == "ankle_dress"


def test_trousers_reach_the_ankle_and_short_sleeves_stop_at_the_elbow():
    import numpy as np

    from bo.bo7_sharing.avatar_dress import ANKLE_Y, SHORT_SLEEVE_X, _reshape

    shorts = np.array([[0.1, 0.95, 0.0], [0.1, 0.70, 0.0], [0.1, 0.53, 0.0]], dtype="f4")
    trousers = _reshape(shorts, "trousers")
    assert abs(trousers[:, 1].min() - ANKLE_Y) < 1e-4 and trousers[0, 1] == shorts[0, 1]  # waist unchanged
    shirt = np.array([[0.0, 1.3, 0.0], [0.6, 1.4, 0.0], [-0.65, 1.4, 0.0]], dtype="f4")
    tee = _reshape(shirt, "short_top")
    assert abs(tee[:, 0]).max() <= SHORT_SLEEVE_X + 1e-6 and tee[0, 0] == 0.0


def test_photo_of_the_piece_becomes_the_garment_texture():
    from bo.bo7_sharing.avatar_dress import _photo_texture

    photo = Image.new("RGB", (100, 100), (255, 255, 255))  # white background
    photo.paste(Image.new("RGB", (60, 80), (20, 120, 30)), (20, 10))  # a green t-shirt
    tex = _photo_texture(photo, (20, 120, 30), size=64)
    r, g, b = tex.getpixel((32, 32))
    assert g > r + 50 and g > b + 50  # the garment shows the piece, not the white background
