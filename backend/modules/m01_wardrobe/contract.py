"""M1 input / output. Used by all 9 BOs: change only through a PR reviewed by the owner (BO3).

`mock.py` and `service.py` both implement exactly the functions listed in `API`, with the same
signatures: they take the request models below and return the response models below.
"""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator, model_validator

from shared.schemas import Color, Garment, GarmentCategory

EMBEDDING_DIM = 512

API = ("classify", "similar", "duplicates", "items", "get_item", "delete_item", "confirm_item",
       "update_item", "extract_document", "embeddings", "embed_texts", "donate_item")

Season = Literal["spring", "summer", "autumn", "winter"]


class ClassifyMode(StrEnum):
    add_to_wardrobe = "add_to_wardrobe"        # store the item in the Item table
    smartbuy_probe = "smartbuy_probe"          # analyse a shop photo, never stored (M6)
    inspiration_photo = "inspiration_photo"    # analyse an inspiration photo, never stored


class OnDuplicate(StrEnum):
    """What add_to_wardrobe does when the photo looks like an item already in the wardrobe."""

    ask = "ask"    # keep the new item `pending` until the user confirms (POST /items/{id}/confirm) or cancels
    add = "add"    # add it anyway (bulk imports, automated BOs)


class ItemStatus(StrEnum):
    pending = "pending"      # possible duplicate waiting for the user's decision; hidden everywhere
    active = "active"
    archived = "archived"
    sold = "sold"
    donated = "donated"


class DonationPlace(StrEnum):
    """Where a donated piece goes (optional, chosen on the confirmation screen)."""

    association = "association"    # a local association
    friend = "friend"              # someone close
    other = "other"


class Shelf(StrEnum):
    """Where the item lives in the wardrobe UI (and any client that mimics it)."""

    accessories = "accessories"   # left, shelves
    clothes = "clothes"           # centre, hanging rail
    shoes = "shoes"               # right, slanted shelves


SHELF_BY_CATEGORY: dict[GarmentCategory, Shelf] = {
    GarmentCategory.top: Shelf.clothes,
    GarmentCategory.bottom: Shelf.clothes,
    GarmentCategory.dress: Shelf.clothes,
    GarmentCategory.outerwear: Shelf.clothes,
    GarmentCategory.traditional: Shelf.clothes,
    GarmentCategory.shoes: Shelf.shoes,
    GarmentCategory.accessory: Shelf.accessories,
}


def shelf_for(category: GarmentCategory | str) -> Shelf:
    return SHELF_BY_CATEGORY[GarmentCategory(category)]


class SizeSystem(StrEnum):
    letter = "letter"        # XS, S, M, L, XL...
    eu = "eu"                # 38, 40...
    fr = "fr"
    us = "us"
    uk = "uk"
    it = "it"
    waist = "waist"          # jeans W32 L34
    shoe_eu = "shoe_eu"      # 42
    shoe_us = "shoe_us"
    one_size = "one_size"
    other = "other"


class Condition(StrEnum):
    new = "new"
    good = "good"
    worn = "worn"
    needs_repair = "needs_repair"


class MaterialShare(BaseModel):
    material: str = Field(min_length=1, description="e.g. linen, cotton, polyester")
    percent: float = Field(gt=0, le=100)


def _round_tnd(v: float | None) -> float | None:
    return None if v is None else round(v, 3)        # TND has 3 decimals (millimes)


class ItemDetails(BaseModel):
    """Information the user adds (form) or that is extracted from a receipt / label (M8)."""

    brand: str | None = Field(default=None, max_length=80)
    size: str | None = Field(default=None, max_length=20,
                             description="as written on the label: M, 40, W32 L34")
    size_system: SizeSystem | None = None
    reference: str | None = Field(default=None, max_length=60, description="SKU / article number")
    purchase_date: date | None = None
    purchase_year: int | None = Field(default=None, ge=1950, le=2100,
                                      description="when only the year is known (old pieces)")
    store: str | None = Field(default=None, max_length=120)
    store_id: str | None = Field(default=None, description="M7 local catalogue shop id, when known")
    composition: list[MaterialShare] = []
    care: list[str] = Field(default=[], description="care instructions, e.g. 'machine wash 30°C'")
    condition: Condition | None = None
    notes: str | None = Field(default=None, max_length=1000)
    receipt_image: str | None = Field(default=None,
                                      description="URL of the kept receipt image (user's choice)")


class WardrobeItem(Garment, ItemDetails):
    """A row of the Item table.

    `status`, `price_tnd` and the ItemDetails fields live here until they are added to
    `shared.schemas.Garment` (separate PR); then this class becomes Garment + `shelf`.
    """

    status: ItemStatus = ItemStatus.active
    price_tnd: float | None = Field(default=None, ge=0)
    donated_at: datetime | None = Field(default=None, description="set by POST /items/{id}/donate")
    donation_place: DonationPlace | None = None

    _price = field_validator("price_tnd")(lambda v: _round_tnd(v))

    @computed_field
    @property
    def shelf(self) -> Shelf:
        return shelf_for(self.category)


class SimilarItem(BaseModel):
    item_id: str
    similarity: float = Field(ge=-1, le=1, description="cosine similarity of the FashionCLIP embeddings")


# --- POST /m01/classify ---------------------------------------------------------------------------

class ClassifyRequest(BaseModel):
    user_id: str = Field(min_length=1)
    image: str = Field(min_length=1, repr=False,
                       description="base64, data URL (data:image/...;base64,...) or http(s) URL")
    mode: ClassifyMode = ClassifyMode.add_to_wardrobe
    price_tnd: float | None = Field(default=None, ge=0, description="optional purchase price, stored as is")
    on_duplicate: OnDuplicate = OnDuplicate.ask


class ClassifyResponse(BaseModel):
    garment: WardrobeItem
    embedding: list[float] = Field(min_length=EMBEDDING_DIM, max_length=EMBEDDING_DIM,
                                   description="FashionCLIP image embedding, L2-normalised")
    needs_confirmation: bool = Field(description="true when confidence < thresholds.confidence")
    duplicates: list[SimilarItem] = Field(default=[], description="existing items above thresholds.duplicate")
    stored: bool = Field(description="true when the item is in the wardrobe (status active)")
    pending: bool = Field(default=False, description=(
        "true when add_to_wardrobe found duplicates and on_duplicate=ask: the item is kept with status "
        "pending, invisible, until POST /m01/items/{item_id}/confirm (accept) or DELETE (cancel)"))
    mocked: bool = False


# --- POST /m01/similar ----------------------------------------------------------------------------

class SimilarRequest(BaseModel):
    user_id: str = Field(min_length=1)
    item_id: str | None = None
    image: str | None = None
    k: int = Field(default=5, ge=1, le=50)
    threshold: float | None = Field(default=None, ge=0, le=1, description="default: thresholds.similar")

    @model_validator(mode="after")
    def _exactly_one_query(self):
        if (self.item_id is None) == (self.image is None):
            raise ValueError("give exactly one of item_id or image")
        return self


class SimilarResponse(BaseModel):
    neighbours: list[SimilarItem]
    mocked: bool = False


# --- POST /m01/duplicates -------------------------------------------------------------------------

class DuplicatesRequest(BaseModel):
    user_id: str = Field(min_length=1)
    threshold: float | None = Field(default=None, ge=0, le=1,
                                    description="default: thresholds.duplicate (0.85)")


class DuplicatesResponse(BaseModel):
    groups: list[list[str]] = Field(description="groups of item_id, each of size >= 2")
    mocked: bool = False


# --- POST /m01/items, GET/DELETE /m01/items/{item_id} ---------------------------------------------

class ItemsRequest(BaseModel):
    user_id: str = Field(min_length=1)
    category: GarmentCategory | None = None
    season: str | None = Field(default=None, description="spring | summer | autumn | winter")
    color: str | None = Field(default=None, description="colour name, e.g. navy")
    status: ItemStatus | None = Field(
        default=None, description="default: every status except pending and donated (the 'À donner' bag)")


class ItemsResponse(BaseModel):
    items: list[WardrobeItem]
    total: int
    mocked: bool = False


class DeleteResponse(BaseModel):
    item_id: str
    deleted: bool
    mocked: bool = False


# --- PATCH /m01/items/{item_id} --------------------------------------------------------------------

class ItemUpdate(BaseModel):
    """Form of the UI: only the fields sent are changed; send null to clear a field.

    Also lets the user correct what the AI guessed (category, season, colours...).
    `receipt_image`: base64 / data URL to keep a receipt image (the user's choice), null to delete it.
    """

    model_config = {"extra": "forbid"}

    # purchase & identity
    price_tnd: float | None = Field(default=None, ge=0)
    brand: str | None = Field(default=None, max_length=80)
    size: str | None = Field(default=None, max_length=20)
    size_system: SizeSystem | None = None
    reference: str | None = Field(default=None, max_length=60)
    purchase_date: date | None = None
    purchase_year: int | None = Field(default=None, ge=1950, le=2100)
    store: str | None = Field(default=None, max_length=120)
    store_id: str | None = None
    composition: list[MaterialShare] | None = None
    care: list[str] | None = None
    condition: Condition | None = None
    notes: str | None = Field(default=None, max_length=1000)
    receipt_image: str | None = Field(default=None, repr=False)
    # corrections of the AI
    category: GarmentCategory | None = None
    subcategory: str | None = Field(default=None, max_length=64)
    season: list[Season] | None = None
    colors: list[Color] | None = None
    pattern: str | None = Field(default=None, max_length=32)
    material: str | None = Field(default=None, max_length=32)
    status: Literal["active", "archived", "sold", "donated"] | None = None

    _price = field_validator("price_tnd")(lambda v: _round_tnd(v))

    @model_validator(mode="after")
    def _composition_total(self):
        if self.composition and sum(m.percent for m in self.composition) > 100.5:
            raise ValueError("composition percentages add up to more than 100")
        return self

    def changes(self) -> dict:
        """The fields the client actually sent (null included)."""
        return {k: getattr(self, k) for k in self.model_fields_set}


# --- POST /m01/items/{item_id}/donate ---------------------------------------------------------------

class DonateRequest(BaseModel):
    """Confirmation screen: the piece goes to the 'À donner' bag (status donated + donated_at)."""

    place: DonationPlace | None = Field(default=None, description="optional: association / friend / other")


# --- POST /m01/items/{item_id}/donation-suggestions (local LLM over a verified list) -------------------

class DonationSuggestionsRequest(BaseModel):
    city: str | None = Field(default=None, max_length=40, description="governorate, e.g. Tunis, Sfax")


class DonationSuggestion(BaseModel):
    place_id: str
    name: str
    type: Literal["association", "community", "collection", "personal"]
    place: DonationPlace = Field(description="value to send to /donate if the user picks this suggestion")
    url: str | None = Field(default=None, description="from donation_places.json, never written by the LLM")
    phone: str | None = None
    address: str | None = None
    how: str
    reason: str = Field(description="why it fits this piece (LLM), or the place's own text without the LLM")


class DonationSuggestionsResponse(BaseModel):
    item_id: str
    city: str | None
    suggestions: list[DonationSuggestion]
    message: str = Field(description="one friendly sentence for the user")
    llm_used: bool = Field(description="false: Ollama unreachable, places in the list's order")
    model: str | None
    elapsed_ms: float


# --- POST /m01/documents/extract (receipt / price tag / care label, through M8) --------------------

class DocumentKind(StrEnum):
    auto = "auto"
    receipt = "receipt"          # ticket de caisse: price, date, store, several lines
    price_tag = "price_tag"      # étiquette prix: price, size, brand, reference
    care_label = "care_label"    # étiquette de composition: materials, care, size


class DocumentRequest(BaseModel):
    user_id: str = Field(min_length=1)
    image: str = Field(min_length=1, repr=False, description="base64, data URL or http(s) URL")
    kind: DocumentKind = DocumentKind.auto
    item_id: str | None = Field(default=None,
                                description="the piece it belongs to: helps pick the receipt line")


class ReceiptLine(BaseModel):
    label: str
    price: float | None = Field(default=None, ge=0)
    quantity: int = Field(default=1, ge=1)


class ExtractedFields(BaseModel):
    """Proposed values: nothing is saved until the user submits the form (PATCH /items/{id})."""

    price: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, description="ISO code; TND -> fills price_tnd")
    purchase_date: date | None = None
    store: str | None = None
    brand: str | None = None
    size: str | None = None
    size_system: SizeSystem | None = None
    reference: str | None = None
    composition: list[MaterialShare] = []
    care: list[str] = []


class DocumentResponse(BaseModel):
    kind: DocumentKind = Field(description="detected kind (never auto)")
    fields: ExtractedFields
    lines: list[ReceiptLine] = Field(default=[], description="receipt lines, when there are several articles")
    selected_line: int | None = Field(default=None,
                                      description="index of the line matching item_id, if found")
    confidence: dict[str, float] = Field(default={}, description="per extracted field, 0..1")
    mocked: bool = False


# --- errors raised by mock.py / service.py (mapped to HTTP codes by router.py) --------------------

class ItemNotFoundError(LookupError):
    """404: unknown item_id for this user."""


class InvalidImageError(ValueError):
    """422: the image cannot be decoded or downloaded."""


class InvalidUpdateError(ValueError):
    """422: the update is not allowed (e.g. changing the status of a pending item)."""


class ExtractionUnavailableError(RuntimeError):
    """503: M8 cannot extract documents right now (not implemented yet, or provider down)."""
