"""Owner: BO7 · puts the BO7 demo garments into M1 (wardrobe, BO3) through M1's public functions.

The 68 demo pieces (56 photos of the Clothing dataset + 12 Tunisian pieces, bo7_sharing/demo_wardrobe/) are
added to the demo user's wardrobe in M1, so M15 and M10 read a real M1 wardrobe:
  1. `classify(add_to_wardrobe, on_duplicate=add)` stores the photo (M1 mock: as is; M1 real: FashionCLIP),
  2. `update_item` sets what the demo already knows: category, name, colours, and the Tunisian maker in
     `brand` (read back as `local_tag` by M15).
Nothing in modules/m01_wardrobe is changed (rule 4: only call the owner's API).
"""

import base64
import json
from pathlib import Path

from shared.schemas import Garment

PHOTOS = Path(__file__).resolve().parent / "demo_wardrobe"
M15 = Path(__file__).resolve().parents[2] / "modules" / "m15_challenges"
FIXTURE = M15 / "tests" / "fixtures" / "wardrobe.json"
DEMO_URL = "http://bo7-demo.local/bo7/demo/photos/"  # how the demo photos are given to M1 in mock mode
DEMO_USERS = {"usr_042", "amen", "yasmine"}  # the demo user and two friends to play challenges with


def demo_garments() -> list[Garment]:
    """The demo pieces that have a photo (fixture items + pieces added from the demo page)."""
    rows = json.loads(FIXTURE.read_text())
    added = PHOTOS / "added.json"
    if added.exists():
        rows += json.loads(added.read_text(encoding="utf-8"))
    out = []
    for r in rows:
        photo = PHOTOS / f"{r['item_id']}.png"
        if photo.exists():
            r = {k: v for k, v in r.items() if k in Garment.model_fields}
            out.append(Garment(user_id="demo", image_raw=str(photo), image_cutout=str(photo), **r))
    return out


def resolve(url: str) -> tuple[str, str] | None:
    """Demo photo URL given to M1 → (URL for the browser, file for the card renderer)."""
    if not url.startswith(DEMO_URL):
        return None
    name = url.removeprefix(DEMO_URL)
    return f"/bo7/demo/photos/{name}", str(PHOTOS / name)


def local_brands() -> set[str]:
    return {g.local_tag for g in demo_garments() if g.local_tag}


async def seed(impl, user_id: str) -> int:
    """Add the demo pieces to `user_id`'s M1 wardrobe (demo users only). Returns the number added."""
    if user_id not in DEMO_USERS:
        return 0
    from modules.m01_wardrobe.contract import ClassifyMode, ClassifyRequest, ItemUpdate, OnDuplicate

    mocked = getattr(impl, "__name__", "").endswith(".mock")
    n = 0
    for g in demo_garments():
        name = Path(g.image_cutout).name
        if mocked:  # M1 mock keeps a URL as is: no copy of the photo on each restart
            image = DEMO_URL + name
        else:  # M1 real: the full pipeline (cutout, FashionCLIP, colours) runs on the photo
            image = "data:image/png;base64," + base64.b64encode(Path(g.image_cutout).read_bytes()).decode()
        res = await impl.classify(
            ClassifyRequest(
                user_id=user_id,
                image=image,
                mode=ClassifyMode.add_to_wardrobe,
                on_duplicate=OnDuplicate.add,
            )
        )
        await impl.update_item(
            user_id,
            res.garment.item_id,
            ItemUpdate(
                category=g.category,
                subcategory=g.subcategory,
                colors=g.colors or None,
                brand=g.local_tag,
            ),
        )
        n += 1
    return n
