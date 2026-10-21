"""mock.py respects the M1 contract on every endpoint."""

import inspect

import pytest

from modules.m01_wardrobe import mock, service
from modules.m01_wardrobe.config import get_config
from modules.m01_wardrobe.contract import (
    API,
    EMBEDDING_DIM,
    ClassifyMode,
    ClassifyRequest,
    ClassifyResponse,
    DeleteResponse,
    DuplicatesRequest,
    DuplicatesResponse,
    ItemNotFoundError,
    ItemsRequest,
    ItemsResponse,
    ItemStatus,
    OnDuplicate,
    Shelf,
    SimilarRequest,
    SimilarResponse,
    WardrobeItem,
)
from shared.schemas import GarmentCategory

from .helpers import png_b64

DEMO = mock.DEMO_USER


def test_mock_and_service_expose_the_same_api():
    for name in API:
        m, s = getattr(mock, name), getattr(service, name)
        assert inspect.iscoroutinefunction(m) and inspect.iscoroutinefunction(s), name
        assert inspect.signature(m) == inspect.signature(s), name


async def test_items_demo_wardrobe():
    out = await mock.items(ItemsRequest(user_id=DEMO))
    assert isinstance(out, ItemsResponse) and out.mocked
    assert out.total == len(out.items) == 13
    cats = {i.category for i in out.items}
    assert {GarmentCategory.traditional, GarmentCategory.shoes, GarmentCategory.accessory} <= cats
    jebba = next(i for i in out.items if i.subcategory == "jebba")
    assert jebba.category == GarmentCategory.traditional and jebba.local_tag == "jebba"
    assert jebba.shelf == Shelf.clothes
    for item in out.items:
        assert item.image_raw.startswith("/m01/ui/assets/") and item.colors
        assert abs(sum(c.share for c in item.colors)) <= 1
    # round-trips through JSON with the computed `shelf`
    ItemsResponse.model_validate(out.model_dump(mode="json"))


@pytest.mark.parametrize(
    ("filters", "expected"),
    [
        ({"category": "shoes"}, {"itm_demo_sneakers_white", "itm_demo_loafers"}),
        ({"color": "navy"}, {"itm_demo_shirt_navy", "itm_demo_shirt_navy_2"}),
        ({"season": "winter", "category": "top"}, {"itm_demo_sweatshirt_grey"}),
    ],
)
async def test_items_filters(filters, expected):
    out = await mock.items(ItemsRequest(user_id=DEMO, **filters))
    assert {i.item_id for i in out.items} == expected


async def test_unknown_user_has_an_empty_wardrobe():
    out = await mock.items(ItemsRequest(user_id="usr_nobody"))
    assert out.total == 0 and out.items == []


async def test_duplicates_finds_the_two_navy_shirts():
    out = await mock.duplicates(DuplicatesRequest(user_id=DEMO))
    assert isinstance(out, DuplicatesResponse) and out.mocked
    assert out.groups == [["itm_demo_shirt_navy", "itm_demo_shirt_navy_2"]]


async def test_similar_by_item_id():
    out = await mock.similar(SimilarRequest(user_id=DEMO, item_id="itm_demo_shirt_navy"))
    assert isinstance(out, SimilarResponse) and out.mocked
    assert out.neighbours[0].item_id == "itm_demo_shirt_navy_2"
    assert out.neighbours[0].similarity > 0.85
    assert all(n.similarity >= 0.75 for n in out.neighbours)
    assert "itm_demo_shirt_navy" not in {n.item_id for n in out.neighbours}


async def test_similar_k_and_threshold():
    out = await mock.similar(SimilarRequest(user_id=DEMO, item_id="itm_demo_bag_brown", k=1, threshold=0))
    assert len(out.neighbours) == 1


async def test_similar_by_image():
    out = await mock.similar(SimilarRequest(user_id=DEMO, image=png_b64(), threshold=0))
    assert len(out.neighbours) == 5


async def test_similar_unknown_item():
    with pytest.raises(ItemNotFoundError):
        await mock.similar(SimilarRequest(user_id=DEMO, item_id="itm_missing"))


async def test_classify_add_to_wardrobe_stores_the_item():
    out = await mock.classify(ClassifyRequest(user_id=DEMO, image=png_b64(data_url=True), price_tnd=42))
    assert isinstance(out, ClassifyResponse) and out.mocked and out.stored
    assert len(out.embedding) == EMBEDDING_DIM
    assert out.needs_confirmation == (out.garment.confidence < get_config().thresholds.confidence)
    assert out.garment.price_tnd == 42
    assert out.garment.image_raw.startswith("/m01/media/usr_demo/")
    assert out.garment.colors[0].name == "navy"           # real LAB K-means on the uploaded pixels
    assert (await mock.items(ItemsRequest(user_id=DEMO))).total == 14


async def test_duplicate_is_pending_until_confirmed():
    image = png_b64(color=(200, 30, 30))
    first = await mock.classify(ClassifyRequest(user_id=DEMO, image=image))
    assert first.stored and not first.pending
    second = await mock.classify(ClassifyRequest(user_id=DEMO, image=image))
    assert first.garment.item_id in {d.item_id for d in second.duplicates}
    assert second.pending and not second.stored and second.garment.status == ItemStatus.pending

    listed = {i.item_id for i in (await mock.items(ItemsRequest(user_id=DEMO))).items}
    assert second.garment.item_id not in listed                                    # hidden while pending
    pending = await mock.items(ItemsRequest(user_id=DEMO, status=ItemStatus.pending))
    assert [i.item_id for i in pending.items] == [second.garment.item_id]
    assert (await mock.duplicates(DuplicatesRequest(user_id=DEMO))).groups == [
        ["itm_demo_shirt_navy", "itm_demo_shirt_navy_2"]]                          # not counted yet

    confirmed = await mock.confirm_item(DEMO, second.garment.item_id)             # accept
    assert confirmed.status == ItemStatus.active
    listed = {i.item_id for i in (await mock.items(ItemsRequest(user_id=DEMO))).items}
    assert second.garment.item_id in listed
    with pytest.raises(ItemNotFoundError):
        await mock.confirm_item(DEMO, second.garment.item_id)                     # already active


async def test_duplicate_can_be_cancelled():
    image = png_b64(color=(30, 160, 30))
    await mock.classify(ClassifyRequest(user_id=DEMO, image=image))
    second = await mock.classify(ClassifyRequest(user_id=DEMO, image=image))
    assert second.pending
    assert (await mock.delete_item(DEMO, second.garment.item_id)).deleted        # cancel
    with pytest.raises(ItemNotFoundError):
        await mock.get_item(DEMO, second.garment.item_id)
    assert (await mock.items(ItemsRequest(user_id=DEMO))).total == 14


async def test_on_duplicate_add_skips_the_question():
    image = png_b64(color=(30, 30, 160))
    await mock.classify(ClassifyRequest(user_id=DEMO, image=image))
    second = await mock.classify(ClassifyRequest(user_id=DEMO, image=image, on_duplicate=OnDuplicate.add))
    assert second.duplicates and second.stored and not second.pending


async def test_classify_portrait_photo_goes_on_the_rail():
    for color in [(10, 10, 10), (120, 40, 40), (40, 120, 40), (40, 40, 120)]:
        out = await mock.classify(ClassifyRequest(user_id=DEMO, image=png_b64(color=color, size=(60, 100))))
        assert out.garment.shelf == Shelf.clothes


async def test_classify_probe_is_not_stored():
    req = ClassifyRequest(user_id=DEMO, image=png_b64(), mode=ClassifyMode.smartbuy_probe)
    out = await mock.classify(req)
    assert not out.stored and out.garment.embedding_id is None
    assert (await mock.items(ItemsRequest(user_id=DEMO))).total == 13


async def test_get_and_delete_item():
    item = await mock.get_item(DEMO, "itm_demo_jebba_white")
    assert isinstance(item, WardrobeItem) and item.item_id == "itm_demo_jebba_white"
    out = await mock.delete_item(DEMO, "itm_demo_jebba_white")
    assert isinstance(out, DeleteResponse) and out.deleted
    with pytest.raises(ItemNotFoundError):
        await mock.get_item(DEMO, "itm_demo_jebba_white")
    with pytest.raises(ItemNotFoundError):
        await mock.delete_item(DEMO, "itm_demo_jebba_white")


def test_similar_request_needs_exactly_one_query():
    with pytest.raises(ValueError):
        SimilarRequest(user_id=DEMO)
    with pytest.raises(ValueError):
        SimilarRequest(user_id=DEMO, item_id="x", image="y")
