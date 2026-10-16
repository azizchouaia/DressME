from modules.m09_avatar_3d.service import render


def test_render_names_the_worn_garments_and_the_thin_body():
    out = render({"user_id": "ada", "payload": {"pose": "standing"}})
    assert out["mocked"] is False
    assert out["result"]["garments"] == ["shirt", "shorts", "vest"]
    assert out["result"]["body"].endswith("smplx_thin.glb")
    assert out["result"]["manifest"]["viewer"]["engine"].startswith("Three.js")
