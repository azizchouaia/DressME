from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.models.clothing_item import ClothingItem
from app.models.outfit import Outfit
from app.schemas.outfit import OutfitCreate, OutfitRead, OutfitUpdate

router = APIRouter(prefix="/outfits", tags=["outfits"])

SLOT_FIELDS = ("shirt_id", "pants_id", "jacket_id", "shoes_id")


def get_owned_outfit(db: DbSession, user: CurrentUser, outfit_id: UUID) -> Outfit:
    outfit = db.get(Outfit, outfit_id)
    if outfit is None or outfit.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Outfit not found.")
    return outfit


def ensure_items_owned(db: DbSession, user: CurrentUser, ids: list[UUID]) -> None:
    if not ids:
        return
    owned = set(
        db.scalars(
            select(ClothingItem.id).where(ClothingItem.user_id == user.id, ClothingItem.id.in_(ids))
        )
    )
    if missing := set(ids) - owned:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"Unknown clothing items: {', '.join(str(i) for i in missing)}",
        )


def _referenced_ids(values: dict[str, object]) -> list[UUID]:
    ids = [v for k, v in values.items() if k in SLOT_FIELDS and isinstance(v, UUID)]
    accessories = values.get("accessory_ids")
    if isinstance(accessories, list):
        ids.extend(a for a in accessories if isinstance(a, UUID))
    return ids


@router.get("", response_model=list[OutfitRead])
def list_outfits(db: DbSession, user: CurrentUser) -> list[Outfit]:
    query = select(Outfit).where(Outfit.user_id == user.id).order_by(Outfit.updated_at.desc())
    return list(db.scalars(query))


@router.post("", response_model=OutfitRead, status_code=status.HTTP_201_CREATED)
def create_outfit(payload: OutfitCreate, db: DbSession, user: CurrentUser) -> Outfit:
    values = payload.model_dump()
    ensure_items_owned(db, user, _referenced_ids(values))
    values["accessory_ids"] = [str(a) for a in payload.accessory_ids]
    outfit = Outfit(user_id=user.id, **values)
    db.add(outfit)
    db.commit()
    return outfit


@router.get("/{outfit_id}", response_model=OutfitRead)
def read_outfit(outfit_id: UUID, db: DbSession, user: CurrentUser) -> Outfit:
    return get_owned_outfit(db, user, outfit_id)


@router.put("/{outfit_id}", response_model=OutfitRead)
def update_outfit(
    outfit_id: UUID, payload: OutfitUpdate, db: DbSession, user: CurrentUser
) -> Outfit:
    outfit = get_owned_outfit(db, user, outfit_id)
    values = payload.model_dump(exclude_unset=True)
    ensure_items_owned(db, user, _referenced_ids(values))
    if "accessory_ids" in values:
        values["accessory_ids"] = [str(a) for a in values["accessory_ids"] or []]
    for field, value in values.items():
        setattr(outfit, field, value)
    db.commit()
    return outfit


@router.delete("/{outfit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_outfit(outfit_id: UUID, db: DbSession, user: CurrentUser) -> None:
    db.delete(get_owned_outfit(db, user, outfit_id))
    db.commit()
