"""Item details (form, PATCH) and receipt / label extraction (through M8)."""

from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from modules.m01_wardrobe import details, m08_client, mock, service
from modules.m01_wardrobe.contract import (
    DocumentKind,
    DocumentRequest,
    DocumentResponse,
    ExtractionUnavailableError,
    InvalidUpdateError,
    ItemNotFoundError,
    ItemStatus,
    ItemUpdate,
    Shelf,
    WardrobeItem,
)
from modules.m01_wardrobe.router import router
from shared.schemas import GarmentCategory

from .helpers import png_b64

DEMO = mock.DEMO_USER


def item(sub: str | None, category="top") -> WardrobeItem:
    return WardrobeItem(item_id="itm_x", user_id="u1", image_raw="x", category=category, subcategory=sub)


# ---------- contract ----------

def test_update_only_contains_the_fields_sent():
    update = ItemUpdate(brand="Zara", notes=None)
    assert update.changes() == {"brand": "Zara", "notes": None}


def test_update_validation():
    assert ItemUpdate(price_tnd=89.12345).price_tnd == 89.123                  # millimes
    with pytest.raises(ValueError):
        ItemUpdate(unknown_field=1)                                             # extra forbidden
    with pytest.raises(ValueError):
        ItemUpdate(season=["monsoon"])
    with pytest.raises(ValueError):
        ItemUpdate(status="pending")                                            # only via /confirm
    with pytest.raises(ValueError):
        ItemUpdate(composition=[{"material": "lin", "percent": 80}, {"material": "coton", "percent": 40}])


# ---------- details: receipt lines ----------

@pytest.mark.parametrize(
    ("sub", "expected"),
    [("linen shirt", 0), ("chinos", 1), ("belt", 2), ("sneakers", None), (None, None)],
)
def test_match_line(sub, expected):
    labels = ["CHEMISE LIN MARINE  M", "CHINO COTON BEIGE 40", "CEINTURE CUIR MARRON"]
    assert details.match_line(labels, item(sub)) == expected


def test_match_line_accents_and_prefixes():
    assert details.match_line(["T-SHIRT BASIC", "ÉCHARPE LAINE"], item("scarf", "accessory")) == 1
    assert details.match_line(["Jebbah homme brodée"], item("jebba", "traditional")) == 0


def test_finalize_takes_the_price_of_the_selected_line():
    doc = DocumentResponse(kind="receipt", fields={}, lines=[{"label": "CHINO BEIGE", "price": 119.9}])
    out = details.finalize(doc, item("chinos", "bottom"))
    assert out.selected_line == 0 and out.fields.price == 119.9 and out.fields.currency == "TND"
    with pytest.raises(ValueError):
        details.finalize(DocumentResponse(kind="auto", fields={}), None)


# ---------- mock ----------

async def test_mock_extract_receipt_picks_the_line_of_the_piece():
    req = DocumentRequest(user_id=DEMO, image=png_b64(), item_id="itm_demo_chino_beige")
    out = await mock.extract_document(req)
    assert out.mocked and out.kind == DocumentKind.receipt
    assert out.selected_line == 1 and out.fields.price == 119.9 and out.fields.currency == "TND"
    assert out.fields.purchase_date == date(2026, 9, 14) and out.fields.brand == "Zara"


@pytest.mark.parametrize(("kind", "field"), [("price_tag", "size"), ("care_label", "composition")])
async def test_mock_extract_labels(kind, field):
    out = await mock.extract_document(DocumentRequest(user_id=DEMO, image=png_b64(), kind=kind))
    assert out.kind == kind and getattr(out.fields, field)


async def test_mock_extract_errors():
    from modules.m01_wardrobe.contract import InvalidImageError

    with pytest.raises(InvalidImageError):
        await mock.extract_document(DocumentRequest(user_id=DEMO, image="not an image"))
    with pytest.raises(ItemNotFoundError):
        await mock.extract_document(DocumentRequest(user_id=DEMO, image=png_b64(), item_id="nope"))


async def test_mock_update_details_and_ai_corrections():
    composition = [{"material": "coton", "percent": 98}, {"material": "élasthanne", "percent": 2}]
    update = ItemUpdate(size="40", size_system="eu", brand="Zara", price_tnd=119.9,
                        purchase_date="2026-09-14",
                        store="Zara · Tunisia Mall", composition=composition,
                        care=["Lavage 30 °C"], condition="good", notes="ourlet refait",
                        category="bottom", subcategory="trousers", season=["spring", "autumn"])
    out = await mock.update_item(DEMO, "itm_demo_chino_beige", update)
    assert (out.size, out.size_system, out.brand, out.price_tnd) == ("40", "eu", "Zara", 119.9)
    assert out.purchase_year == 2026 and out.condition == "good" and out.composition[0].percent == 98
    assert out.subcategory == "trousers" and out.season == ["spring", "autumn"]
    assert (await mock.get_item(DEMO, "itm_demo_chino_beige")).brand == "Zara"          # persisted


async def test_mock_update_moves_the_piece_when_the_category_is_corrected():
    out = await mock.update_item(DEMO, "itm_demo_sneakers_white", ItemUpdate(category="accessory"))
    assert out.shelf == Shelf.accessories


async def test_mock_update_clears_fields_and_old_pieces_keep_only_the_year():
    await mock.update_item(DEMO, "itm_demo_jeans_blue", ItemUpdate(brand="Levi's", care=["30 °C"]))
    clear = ItemUpdate(brand=None, care=None, purchase_year=2015)
    out = await mock.update_item(DEMO, "itm_demo_jeans_blue", clear)
    assert out.brand is None and out.care == [] and out.purchase_year == 2015 and out.purchase_date is None


async def test_mock_receipt_image_is_kept_only_if_the_user_wants(tmp_path):
    keep = ItemUpdate(receipt_image=png_b64(data_url=True))
    out = await mock.update_item(DEMO, "itm_demo_shirt_navy", keep)
    assert out.receipt_image == "/m01/media/usr_demo/itm_demo_shirt_navy_receipt.jpg"
    saved = tmp_path / "m01" / "media" / "usr_demo" / "itm_demo_shirt_navy_receipt.jpg"
    assert saved.exists()
    out = await mock.update_item(DEMO, "itm_demo_shirt_navy", ItemUpdate(brand="Zara"))   # untouched
    assert out.receipt_image is not None and saved.exists()
    out = await mock.update_item(DEMO, "itm_demo_shirt_navy", ItemUpdate(receipt_image=None))
    assert out.receipt_image is None and not saved.exists()


async def test_mock_update_errors():
    with pytest.raises(ItemNotFoundError):
        await mock.update_item(DEMO, "nope", ItemUpdate(brand="x"))
    with pytest.raises(InvalidUpdateError):
        await mock.update_item(DEMO, "itm_demo_belt_brown", ItemUpdate(category=None))


async def test_pending_item_cannot_be_activated_by_patch():
    image = png_b64(color=(10, 200, 200))
    await mock.classify(mock.ClassifyRequest(user_id=DEMO, image=image))
    held = await mock.classify(mock.ClassifyRequest(user_id=DEMO, image=image))
    assert held.pending
    with pytest.raises(InvalidUpdateError):
        await mock.update_item(DEMO, held.garment.item_id, ItemUpdate(status="active"))
    out = await mock.update_item(DEMO, held.garment.item_id, ItemUpdate(size="M"))      # details are fine
    assert out.status == ItemStatus.pending and out.size == "M"


# ---------- service (store and M8 faked) ----------

class DetailsStore:
    def __init__(self):
        self.items = {"itm_a": WardrobeItem(item_id="itm_a", user_id="u1", image_raw="x", category="bottom",
                                            subcategory="chinos")}
        self.written: dict = {}

    async def ensure_schema(self):
        pass

    async def get_item(self, user_id, item_id):
        return self.items.get(item_id) if user_id == "u1" else None

    async def update_item(self, user_id, item_id, values):
        self.written = values
        return WardrobeItem.model_validate(self.items[item_id].model_dump(exclude={"shelf"}) | values)


@pytest.fixture
def details_store(monkeypatch):
    st = DetailsStore()
    monkeypatch.setattr(service, "store", st)
    return st


async def test_service_update_writes_plain_values(details_store):
    update = ItemUpdate(purchase_date="2026-09-14", composition=[{"material": "coton", "percent": 100}],
                        size_system="eu", category=GarmentCategory.bottom)
    out = await service.update_item("u1", "itm_a", update)
    assert details_store.written["composition"] == [{"material": "coton", "percent": 100.0}]
    assert details_store.written["size_system"] == "eu" and details_store.written["category"] == "bottom"
    assert details_store.written["purchase_date"] == date(2026, 9, 14)
    assert details_store.written["purchase_year"] == 2026 and out.purchase_year == 2026
    with pytest.raises(ItemNotFoundError):
        await service.update_item("someone_else", "itm_a", ItemUpdate(brand="x"))


async def test_service_extract_goes_through_m08(details_store, monkeypatch):
    seen = {}

    def parse(req):
        seen.update(req)
        lines = [{"label": "T-SHIRT", "price": 29.9}, {"label": "CHINO BEIGE 40", "price": 119.9}]
        return {"result": {"kind": "receipt", "fields": {"store": "Zara"}, "lines": lines}}

    monkeypatch.setattr(m08_client, "_m08", lambda: type("M8", (), {"parse": staticmethod(parse)}))
    out = await service.extract_document(DocumentRequest(user_id="u1", image=png_b64(), item_id="itm_a"))
    assert not out.mocked and out.selected_line == 1 and out.fields.price == 119.9
    payload = seen["payload"]
    assert payload["task"] == m08_client.TASK and payload["image"].startswith("data:image/jpeg;base64,")
    assert payload["hint"]["subcategory"] == "chinos" and payload["kind"] == "auto"


async def test_service_extract_is_unavailable_while_m08_is_a_stub(details_store):
    # the real M8 module (its mock returns {"todo": ...}, its service raises NotImplementedError)
    with pytest.raises(ExtractionUnavailableError):
        await service.extract_document(DocumentRequest(user_id="u1", image=png_b64()))


async def test_service_extract_rejects_an_invalid_m8_answer(details_store, monkeypatch):
    bad = {"result": {"kind": "receipt", "fields": {"price": -3}}}
    monkeypatch.setattr(m08_client, "_m08", lambda: type("M8", (), {"parse": staticmethod(lambda r: bad)}))
    with pytest.raises(ExtractionUnavailableError):
        await service.extract_document(DocumentRequest(user_id="u1", image=png_b64()))


# ---------- HTTP ----------

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_http_patch_and_extract(client):
    url = "/m01/items/itm_demo_loafers"
    form = {"size": "42", "size_system": "shoe_eu", "brand": "Clarks"}
    r = client.patch(url, params={"user_id": DEMO}, json=form)
    assert r.status_code == 200 and r.json()["size"] == "42" and r.json()["shelf"] == "shoes"
    assert client.get(url, params={"user_id": DEMO}).json()["brand"] == "Clarks"
    assert client.patch(url, params={"user_id": DEMO}, json={"colour": "x"}).status_code == 422
    assert client.patch("/m01/items/nope", params={"user_id": DEMO}, json={}).status_code == 404

    body = {"user_id": DEMO, "image": png_b64(), "kind": "care_label", "item_id": "itm_demo_loafers"}
    r = client.post("/m01/documents/extract", json=body)
    assert r.status_code == 200 and r.json()["fields"]["composition"]


def test_http_extract_is_503_in_real_mode_until_m8_supports_it(client, monkeypatch):
    monkeypatch.setenv("M01_USE_MOCKS", "false")
    r = client.post("/m01/documents/extract", json={"user_id": DEMO, "image": png_b64()})
    assert r.status_code == 503 and "M8" in r.json()["detail"]
