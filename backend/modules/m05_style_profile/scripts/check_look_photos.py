"""Checks the reference looks: where each vector comes from (photo or description), which style it lands on.

Each look should land on its own style; a photo that lands elsewhere misleads the onboarding swipes (a like on
it would teach the wrong style). Only meaningful with real FashionCLIP (the M1 mock has random vectors):

    cd backend && M01_USE_MOCKS=false python -m modules.m05_style_profile.scripts.check_look_photos
"""

import asyncio

import numpy as np

from modules.m05_style_profile import m01_client, service, styles
from modules.m05_style_profile.config import load_reference_looks


async def check() -> list[dict]:
    """One row per look: id, style it was made for, vector source, top style found, its share, ok."""
    space = await styles.get_space()
    defs = {d.id: d for d in load_reference_looks()}
    rows = []
    for lk in await service.reference_looks(reseed=True):
        mix = space.mix(np.asarray(lk.embedding))
        top = space.ids[int(np.argmax(mix))]
        rows.append(
            {
                "id": lk.id,
                "style": lk.style_id,
                "source": "photo" if service._embed_from_photo(defs[lk.id]) else "description",
                "found": top,
                "share": round(float(mix.max()), 2),
                "ok": top == lk.style_id,
            }
        )
    return rows


async def main() -> None:
    rows = await check()
    print(f"M1 {m01_client.mode()}: {sum(r['ok'] for r in rows)}/{len(rows)} looks land on their own style")
    for r in rows:
        mark = "ok " if r["ok"] else "BAD"
        found = f"found {r['found']} {r['share']:.0%}"
        print(f"  {mark} {r['id']:20s} {r['source']:11s} made for {r['style']:13s} {found}")
    if m01_client.mode() == "mock":
        print("(M1 mock: random vectors, run with M01_USE_MOCKS=false for a real check)")


if __name__ == "__main__":
    asyncio.run(main())
