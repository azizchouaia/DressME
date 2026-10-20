"""service.py and pipeline logic with mocked models / store. Real models: @pytest.mark.slow."""

import numpy as np
import pytest

from modules.m01_wardrobe import service
from modules.m01_wardrobe.config import get_config
from modules.m01_wardrobe.contract import (
    EMBEDDING_DIM,
    ClassifyMode,
    ClassifyRequest,
    DuplicatesRequest,
    ItemNotFoundError,
    ItemsRequest,
    ItemStatus,
    OnDuplicate,
    Shelf,
    SimilarItem,
    SimilarRequest,
    WardrobeItem,
    shelf_for,
)
from modules.m01_wardrobe.pipeline import images
from modules.m01_wardrobe.pipeline.classifier import Attributes, describe
from modules.m01_wardrobe.pipeline.colors import dominant_colors, name_color, srgb_to_lab
from modules.m01_wardrobe.pipeline.dedup import UnionFind, group_pairs, pairs_above
from shared.schemas import Color, GarmentCategory

from .helpers import png_b64

# ---------- shelves ----------

@pytest.mark.parametrize(
    ("category", "shelf"),
    [
        ("top", Shelf.clothes), ("bottom", Shelf.clothes), ("dress", Shelf.clothes),
        ("outerwear", Shelf.clothes), ("traditional", Shelf.clothes),
        ("shoes", Shelf.shoes), ("accessory", Shelf.accessories),
    ],
)
def test_category_to_shelf(category, shelf):
    assert shelf_for(category) == shelf


def test_every_category_has_a_shelf():
    assert {shelf_for(c) for c in GarmentCategory} == set(Shelf)


# ---------- config ----------

def test_config_labels_and_thresholds():
    cfg = get_config()
    assert cfg.thresholds.duplicate == 0.85 and cfg.thresholds.similar == 0.75
    traditional = {s.label for s in cfg.subcategories if s.category == GarmentCategory.traditional}
    assert {"jebba", "kachabia", "sefsari", "blouza"} <= traditional
    assert {s.category for s in cfg.subcategories} == set(GarmentCategory)
    assert cfg.subcategories[0].text(cfg.prompt_template) == "a photo of a t-shirt"
    labels = [s.label for s in cfg.subcategories]
    assert len(labels) == len(set(labels))


# ---------- colours ----------

def test_srgb_to_lab_reference_values():
    np.testing.assert_allclose(srgb_to_lab(np.array([255, 255, 255])), [100, 0, 0], atol=0.05)
    np.testing.assert_allclose(srgb_to_lab(np.array([0, 0, 0])), [0, 0, 0], atol=0.05)
    np.testing.assert_allclose(srgb_to_lab(np.array([255, 0, 0])), [53.24, 80.09, 67.20], atol=0.1)


def test_name_color_uses_palette():
    palette = get_config().palette
    assert name_color(srgb_to_lab(np.array([30, 42, 70])), palette) == "navy"
    assert name_color(srgb_to_lab(np.array([250, 250, 250])), palette) == "white"


def test_dominant_colors_only_use_the_mask():
    img = np.zeros((60, 60, 4), dtype=np.uint8)
    img[..., :3] = (200, 20, 20)                     # red background ...
    img[..., 3] = 0                                  # ... fully transparent: must be ignored
    img[10:50, 10:38] = (31, 42, 68, 255)            # 40x28 navy
    img[10:50, 38:50] = (247, 247, 245, 255)         # 40x12 white
    colors = dominant_colors(img, get_config().palette)
    assert [c.name for c in colors] == ["navy", "white"]
    assert colors[0].share == pytest.approx(0.7, abs=0.01)
    assert colors[1].share == pytest.approx(0.3, abs=0.01)
    assert colors[0].hex == "#1F2A44"


def test_dominant_colors_empty_mask():
    assert dominant_colors(np.zeros((8, 8, 4), dtype=np.uint8), get_config().palette) == []


# ---------- union-find ----------

def test_union_find():
    uf = UnionFind()
    uf.union("a", "b")
    uf.union("c", "b")
    assert uf.find("a") == uf.find("c")
    assert uf.find("d") == "d"


def test_group_pairs_transitive_and_sorted():
    groups = group_pairs([("b", "a"), ("c", "b"), ("e", "d"), ("x", "x")])
    assert groups == [["a", "b", "c"], ["d", "e"]]
    assert group_pairs([]) == []


def test_pairs_above_threshold():
    v = np.array([[1, 0, 0], [0.9, np.sqrt(1 - 0.81), 0], [0, 0, 1]])
    assert pairs_above(["a", "b", "c"], v, 0.85) == [("a", "b")]
    assert pairs_above(["a", "b", "c"], v, 0.95) == []
    assert pairs_above(["a"], v[:1], 0.5) == []


# ---------- zero-shot classifier ----------

class FakeClip:
    """zero_shot() favours the prompts containing one of `wanted`."""

    def __init__(self, *wanted):
        self.wanted = wanted
        self.scales = []

    def zero_shot(self, image_emb, prompts, scale=None):
        self.scales.append(scale)
        scores = np.array([5.0 if any(w in p for w in self.wanted) else 0.0 for p in prompts])
        z = np.exp(scores - scores.max())
        return z / z.sum()


def test_describe_tunisian_jebba():
    attrs = describe(FakeClip("jebba", "summer", "embroidered", "silk", "formal ceremony"), np.zeros(4))
    assert attrs.category == GarmentCategory.traditional
    assert attrs.subcategory == "jebba" and attrs.local_tag == "jebba"
    assert attrs.season == ["summer"] and attrs.pattern == "embroidered" and attrs.material == "silk"
    assert attrs.formality > 0.9
    assert attrs.confidence > 0.7


def test_describe_uses_the_configured_logit_scales():
    clip = FakeClip("shirt")
    describe(clip, np.zeros(4))
    # subcategories, seasons, patterns, materials, formality
    assert clip.scales == [None, 25, None, None, 50]


def test_describe_category_is_the_sum_of_its_subcategories():
    # one shoe prompt vs several accessory prompts with the same score: the accessory family wins
    clip = FakeClip("sneakers", "handbag", "leather belt", "sunglasses")
    attrs = describe(clip, np.zeros(4))
    assert attrs.category == GarmentCategory.accessory
    assert attrs.subcategory in {"bag", "belt", "sunglasses"}


def test_describe_uniform_probs_has_low_confidence():
    attrs = describe(FakeClip(), np.zeros(4))
    assert attrs.confidence < get_config().thresholds.confidence
    assert attrs.season == ["spring", "summer", "autumn", "winter"]
    assert attrs.formality == pytest.approx(0.5)


# ---------- cutout ----------

def test_crop_to_mask():
    from PIL import Image

    from modules.m01_wardrobe.pipeline.cutout import crop_to_mask

    img = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
    img.paste((255, 0, 0, 255), (50, 20, 150, 80))           # 100 x 60 opaque box
    out = crop_to_mask(img)
    assert out.size == (106, 66)                              # 3 % margin on each side
    assert crop_to_mask(Image.new("RGBA", (10, 10))).size == (10, 10)


# ---------- images ----------

def test_read_image_bytes_accepts_base64_and_data_url():
    assert images.read_image_bytes(png_b64()) == images.read_image_bytes(png_b64(data_url=True))


@pytest.mark.parametrize("bad", ["not base64 !!", "aGVsbG8="])
def test_invalid_images(bad):
    from modules.m01_wardrobe.contract import InvalidImageError

    with pytest.raises(InvalidImageError):
        images.open_image(images.read_image_bytes(bad))


def test_private_urls_are_refused():
    from modules.m01_wardrobe.contract import InvalidImageError

    with pytest.raises(InvalidImageError):
        images.read_image_bytes("http://127.0.0.1/admin.png")


# ---------- service with mocked pipeline + store ----------

class FakeStore:
    def __init__(self, neighbours=(), pairs=()):
        self.added, self.neighbours, self.pairs = [], list(neighbours), list(pairs)
        self.pending: set[str] = set()
        self.embeddings = {"itm_a": [1.0] + [0.0] * (EMBEDDING_DIM - 1)}

    async def ensure_schema(self):
        pass

    async def nearest(self, user_id, vector, k, min_similarity, exclude_id=None):
        return [n for n in self.neighbours if n.similarity >= min_similarity and n.item_id != exclude_id][:k]

    async def add_item(self, item, embedding):
        self.added.append((item, list(embedding)))
        return item

    async def get_embedding(self, user_id, item_id):
        return self.embeddings.get(item_id)

    async def duplicate_pairs(self, user_id, threshold):
        return self.pairs

    async def list_items(self, req):
        return [item for item, _ in self.added]

    async def get_item(self, user_id, item_id):
        return None

    async def set_status(self, user_id, item_id, from_status, to_status):
        if from_status != "pending" or item_id not in self.pending:
            return None
        self.pending.discard(item_id)
        return WardrobeItem(item_id=item_id, user_id=user_id, image_raw="x", category="top", status=to_status)

    async def delete_item(self, user_id, item_id):
        return False


def fake_analysis(confidence=0.9):
    emb = np.zeros(EMBEDDING_DIM, dtype=np.float32)
    emb[0] = 1
    attrs = Attributes(GarmentCategory.top, "linen shirt", None, confidence, ["summer"], "solid", "linen",
                       0.55)
    colors = [Color(name="navy", hex="#1F2A44", share=0.9)]
    return service.Analysis(b"raw", "jpg", b"cutout", attrs, colors, emb)


@pytest.fixture
def fake_store(monkeypatch):
    store = FakeStore(neighbours=[
        SimilarItem(item_id="itm_old", similarity=0.91),
        SimilarItem(item_id="itm_far", similarity=0.6),
    ])
    monkeypatch.setattr(service, "store", store)
    return store


async def test_service_classify_add_to_wardrobe(monkeypatch, fake_store):
    monkeypatch.setattr(service, "_analyse", lambda data, full=True: fake_analysis())
    req = ClassifyRequest(user_id="u1", image=png_b64(), price_tnd=89, on_duplicate=OnDuplicate.add)
    out = await service.classify(req)
    assert out.stored and not out.pending and not out.needs_confirmation and not out.mocked
    assert out.garment.status == ItemStatus.active
    assert out.garment.category == GarmentCategory.top and out.garment.shelf == Shelf.clothes
    assert out.garment.image_raw.endswith("_raw.jpg") and out.garment.image_cutout.endswith("_cutout.png")
    assert out.garment.embedding_id == out.garment.item_id
    assert [d.item_id for d in out.duplicates] == ["itm_old"]           # only >= 0.85
    assert len(out.embedding) == EMBEDDING_DIM
    assert len(fake_store.added) == 1 and fake_store.added[0][0].price_tnd == 89


async def test_service_classify_duplicate_is_held_pending(monkeypatch, fake_store):
    monkeypatch.setattr(service, "_analyse", lambda data, full=True: fake_analysis())
    out = await service.classify(ClassifyRequest(user_id="u1", image=png_b64()))      # on_duplicate=ask
    assert out.pending and not out.stored
    assert out.garment.status == ItemStatus.pending
    assert [d.item_id for d in out.duplicates] == ["itm_old"]
    assert fake_store.added[0][0].status == ItemStatus.pending                         # kept, but hidden


async def test_service_classify_without_duplicate_is_added(monkeypatch):
    monkeypatch.setattr(service, "store", FakeStore())
    monkeypatch.setattr(service, "_analyse", lambda data, full=True: fake_analysis())
    out = await service.classify(ClassifyRequest(user_id="u1", image=png_b64()))
    assert out.stored and not out.pending and out.garment.status == ItemStatus.active


async def test_service_confirm_item(fake_store):
    fake_store.pending = {"itm_new"}
    item = await service.confirm_item("u1", "itm_new")
    assert item.status == ItemStatus.active
    with pytest.raises(ItemNotFoundError):
        await service.confirm_item("u1", "itm_new")                    # no longer pending


async def test_service_classify_probe_low_confidence(monkeypatch, fake_store):
    monkeypatch.setattr(service, "_analyse", lambda data, full=True: fake_analysis(confidence=0.3))
    req = ClassifyRequest(user_id="u1", image=png_b64(), mode=ClassifyMode.smartbuy_probe)
    out = await service.classify(req)
    assert not out.stored and out.needs_confirmation
    assert out.garment.image_raw == "inline" and fake_store.added == []


async def test_service_similar_by_item_and_unknown(fake_store):
    out = await service.similar(SimilarRequest(user_id="u1", item_id="itm_a"))
    assert [n.item_id for n in out.neighbours] == ["itm_old"]           # default threshold 0.75
    out = await service.similar(SimilarRequest(user_id="u1", item_id="itm_a", threshold=0.5))
    assert len(out.neighbours) == 2
    with pytest.raises(ItemNotFoundError):
        await service.similar(SimilarRequest(user_id="u1", item_id="itm_missing"))


async def test_service_duplicates_groups(monkeypatch):
    monkeypatch.setattr(service, "store", FakeStore(pairs=[("i2", "i1"), ("i3", "i2"), ("i8", "i9")]))
    out = await service.duplicates(DuplicatesRequest(user_id="u1"))
    assert out.groups == [["i1", "i2", "i3"], ["i8", "i9"]]


async def test_service_items_and_not_found(fake_store):
    assert (await service.items(ItemsRequest(user_id="u1"))).total == 0
    with pytest.raises(ItemNotFoundError):
        await service.get_item("u1", "nope")
    with pytest.raises(ItemNotFoundError):
        await service.delete_item("u1", "nope")


# ---------- real models (download ~600 MB the first time) ----------

@pytest.mark.slow
def test_real_pipeline_end_to_end():
    pytest.importorskip("rembg")
    pytest.importorskip("transformers")
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (256, 256), (240, 240, 240))
    ImageDraw.Draw(img).polygon([(80, 40), (176, 40), (210, 110), (180, 120), (176, 230), (80, 230),
                                 (76, 120), (46, 110)], fill=(31, 42, 68))
    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    a = service._analyse(buf.getvalue())
    assert a.embedding.shape == (EMBEDDING_DIM,)
    assert np.linalg.norm(a.embedding) == pytest.approx(1, abs=1e-4)
    assert a.attributes.category in set(GarmentCategory)
    assert a.colors and a.colors[0].name in {"navy", "blue", "denim", "charcoal"}
