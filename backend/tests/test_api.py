import io

from fastapi.testclient import TestClient
from PIL import Image


def test_register_login_and_me(client: TestClient) -> None:
    payload = {"email": "Bo@Example.com", "password": "long-enough", "display_name": "Bo"}
    assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409

    bad = client.post("/api/v1/auth/login", json={"email": "bo@example.com", "password": "nope"})
    assert bad.status_code == 401

    login = client.post(
        "/api/v1/auth/login", json={"email": "bo@example.com", "password": "long-enough"}
    )
    token = login.json()["access_token"]
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["display_name"] == "Bo"


def test_requires_auth(client: TestClient) -> None:
    assert client.get("/api/v1/wardrobe").status_code == 401


def test_demo_login(client: TestClient) -> None:
    response = client.post("/api/v1/auth/demo")
    assert response.status_code == 200
    assert response.json()["user"]["display_name"] == "Nadhir"


def test_new_user_gets_sample_wardrobe_with_3d_assets(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    items = client.get("/api/v1/wardrobe", headers=auth_headers).json()
    assert len(items) == 9
    assert all(item["glb_url"].endswith(".glb") for item in items)

    jeans = client.get("/api/v1/wardrobe?category=jeans", headers=auth_headers).json()
    assert {i["name"] for i in jeans} == {"Blue jeans", "Black jeans"}


def test_upload_analyze_and_confirm(client: TestClient, auth_headers: dict[str, str]) -> None:
    image = Image.new("RGB", (200, 200), (245, 245, 245))
    for x in range(50, 150):
        for y in range(40, 170):
            image.putpixel((x, y), (180, 40, 45))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    upload = client.post(
        "/api/v1/wardrobe/upload",
        headers=auth_headers,
        files={"image": ("shirt.png", buffer.getvalue(), "image/png")},
    )
    assert upload.status_code == 201, upload.text
    item = upload.json()
    assert item["status"] == "uploaded"
    assert item["glb_url"] is None
    assert client.get(item["thumbnail_url"]).status_code == 200

    analysis = client.post(f"/api/v1/wardrobe/{item['id']}/analyze", headers=auth_headers).json()
    assert analysis["primary_color"] == "red"

    # Analysis is a suggestion only: confirmed fields stay untouched.
    stored = client.get(f"/api/v1/wardrobe/{item['id']}", headers=auth_headers).json()
    assert stored["color"] is None
    assert stored["status"] == "analyzed"

    confirmed = client.put(
        f"/api/v1/wardrobe/{item['id']}",
        headers=auth_headers,
        json={"name": "Red tee", "category": "t-shirt", "color": "red"},
    ).json()
    assert confirmed["name"] == "Red tee"
    assert confirmed["category"] == "t-shirt"

    assert client.delete(f"/api/v1/wardrobe/{item['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/v1/wardrobe/{item['id']}", headers=auth_headers).status_code == 404


def test_upload_rejects_non_image(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/v1/wardrobe/upload",
        headers=auth_headers,
        files={"image": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 422


def test_outfit_crud_and_single_slot_replacement(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    items = {i["name"]: i["id"] for i in client.get("/api/v1/wardrobe", headers=auth_headers).json()}
    outfit = client.post(
        "/api/v1/outfits",
        headers=auth_headers,
        json={
            "name": "Weekend",
            "shirt_id": items["Black T-shirt"],
            "pants_id": items["Blue jeans"],
            "shoes_id": items["White sneakers"],
        },
    ).json()

    updated = client.put(
        f"/api/v1/outfits/{outfit['id']}",
        headers=auth_headers,
        json={"shirt_id": items["White T-shirt"]},
    ).json()
    assert updated["shirt_id"] == items["White T-shirt"]
    assert updated["pants_id"] == items["Blue jeans"]
    assert updated["shoes_id"] == items["White sneakers"]

    cleared = client.put(
        f"/api/v1/outfits/{outfit['id']}", headers=auth_headers, json={"shoes_id": None}
    ).json()
    assert cleared["shoes_id"] is None

    names = [o["name"] for o in client.get("/api/v1/outfits", headers=auth_headers).json()]
    assert "Weekend" in names
    assert client.delete(f"/api/v1/outfits/{outfit['id']}", headers=auth_headers).status_code == 204


def test_outfit_rejects_foreign_items(client: TestClient, auth_headers: dict[str, str]) -> None:
    other = client.post(
        "/api/v1/auth/register",
        json={"email": "eve@example.com", "password": "password123", "display_name": "Eve"},
    ).json()
    eve_headers = {"Authorization": f"Bearer {other['access_token']}"}
    eve_item = client.get("/api/v1/wardrobe", headers=eve_headers).json()[0]["id"]

    response = client.post(
        "/api/v1/outfits", headers=auth_headers, json={"name": "Stolen", "shirt_id": eve_item}
    )
    assert response.status_code == 422


def test_body_profile_drives_avatar(client: TestClient, auth_headers: dict[str, str]) -> None:
    profile = client.get("/api/v1/body-profile", headers=auth_headers).json()
    assert profile["avatar_preset"] == "average"

    client.put(
        "/api/v1/body-profile",
        headers=auth_headers,
        json={"height_cm": 160, "chest_cm": 110, "avatar_preset": "broad"},
    )
    avatar = client.get("/api/v1/avatar", headers=auth_headers).json()
    assert avatar["preset"] == "broad"
    assert avatar["scale"]["x"] == 1
    assert avatar["scale"]["y"] < 1
    assert avatar["parameters"]["chest_ratio"] > 1
    assert avatar["parameters"]["depth_ratio"] > 1
    assert avatar["base_model_url"].endswith("base_avatar.glb")
    assert avatar["from_photo"] is False


def test_process_3d_stays_unavailable_without_the_model(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    image = Image.new("RGB", (32, 32), (20, 40, 180))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    item = client.post(
        "/api/v1/wardrobe/upload",
        headers=auth_headers,
        files={"image": ("swatch.png", buffer.getvalue(), "image/png")},
    ).json()

    response = client.post(f"/api/v1/garments/{item['id']}/process-3d", headers=auth_headers)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["glb_url"] is None
    assert "not available" in body["message"]


def test_photo_preview_keeps_the_wearable_body(client: TestClient, auth_headers: dict[str, str]) -> None:
    image = Image.new("RGB", (32, 32), (180, 140, 120))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    blocked = client.post(
        "/api/v1/avatar/from-photo",
        headers=auth_headers,
        files={"image": ("person.png", buffer.getvalue(), "image/png")},
    )
    assert blocked.status_code == 503

    from app.db.session import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == "ada@example.com").one()
        user.body_profile.avatar_glb_url = "/media/avatars/ada/body.glb"
        db.commit()
    finally:
        db.close()

    avatar = client.get("/api/v1/avatar", headers=auth_headers).json()
    assert avatar["base_model_url"].endswith("body.glb")
    assert avatar["photo_model_url"].endswith("body.glb")
    assert avatar["from_photo"] is True

    cleared = client.delete("/api/v1/avatar/from-photo", headers=auth_headers)
    assert cleared.status_code == 200
    assert cleared.json()["from_photo"] is False
    assert cleared.json()["photo_model_url"] is None


def test_models_and_viewer_are_served(client: TestClient) -> None:
    viewer = client.get("/viewer/")
    assert viewer.status_code == 200
    assert "canvas" in viewer.text

    model = client.get("/models/avatar/base_avatar.glb")
    assert model.status_code == 200
    assert model.content.startswith(b"glTF")


def test_stylist_builds_an_outfit_from_the_wardrobe(client: TestClient, auth_headers: dict[str, str], monkeypatch) -> None:
    import numpy as np

    class StandIn:
        def embed_text(self, text: str):
            vector = np.ones(4, dtype=np.float32)
            return vector / np.linalg.norm(vector)

        def embed_image(self, data: bytes):
            return self.embed_text("image")

    monkeypatch.setattr("app.api.routes.stylist.build_embedder", lambda: StandIn())
    assert client.post("/api/v1/stylist/chat", data={"message": "what should I wear"}).status_code == 401
    response = client.post(
        "/api/v1/stylist/chat",
        headers=auth_headers,
        data={"message": "what should I wear", "weather": "rainy", "season": "autumn", "occasion": "office"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "wear" in body["reply"].lower() or body["outfit"]
    assert {piece["slot"] for piece in body["outfit"]} >= {"top", "bottom"}


def test_garment_3d_status(client: TestClient, auth_headers: dict[str, str]) -> None:
    item = client.get("/api/v1/wardrobe", headers=auth_headers).json()[0]
    status = client.get(f"/api/v1/garments/{item['id']}/3d-status", headers=auth_headers).json()
    assert status["glb_url"] == item["glb_url"]
