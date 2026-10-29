"""Bridge to M1 (wardrobe, owner BO3), in-process like M1 -> M8. M5 never reads M1's tables or models.

Follows M1's own switch: M1's mock.py when M1 is mocked (USE_MOCKS / M01_USE_MOCKS), service.py otherwise.
"""

import numpy as np

from shared.config import settings


def _m01():
    from modules.m01_wardrobe import mock, service
    from modules.m01_wardrobe.config import use_mocks

    return mock if use_mocks(getattr(settings, "use_mocks", True)) else service


def mode() -> str:
    from modules.m01_wardrobe.config import use_mocks

    return "mock" if use_mocks(getattr(settings, "use_mocks", True)) else "real"


async def items(user_id: str) -> list:
    """Active items of the user (M1 WardrobeItem), oldest first."""
    from modules.m01_wardrobe.contract import ItemsRequest, ItemStatus

    return (await _m01().items(ItemsRequest(user_id=user_id, status=ItemStatus.active))).items


async def embeddings(user_id: str, item_ids: list[str] | None = None) -> dict[str, np.ndarray]:
    found = await _m01().embeddings(user_id, item_ids)
    return {i: np.asarray(v, dtype=float) for i, v in found.items()}


async def embed_texts(texts: list[str]) -> np.ndarray:
    return np.asarray(await _m01().embed_texts(list(texts)), dtype=float)


async def embed_images(images: list[str], user_id: str = "m05_system") -> np.ndarray:
    """FashionCLIP embeddings of photos (URL / base64), through M1 classify in a non-storing mode."""
    from modules.m01_wardrobe.contract import ClassifyMode, ClassifyRequest

    out = []
    for image in images:
        res = await _m01().classify(
            ClassifyRequest(user_id=user_id, image=image, mode=ClassifyMode.inspiration_photo)
        )
        out.append(res.embedding)
    return np.asarray(out, dtype=float)
