"""Seeds the reference_look table from reference_looks.json (embeddings through M1's FashionCLIP).

M5 also seeds it lazily on first use; run this after editing the looks, or to warm a fresh database.
Uses the same mode switches as the API (USE_MOCKS / M01_USE_MOCKS, DATABASE_URL, M05_STORE):

    cd backend && M01_USE_MOCKS=false python -m modules.m05_style_profile.scripts.seed_reference_looks
"""

import asyncio

from modules.m05_style_profile import m01_client, service
from modules.m05_style_profile.repository import get_store


async def main() -> None:
    looks = await service.reference_looks(reseed=True)
    store, mode = type(get_store()).__name__, m01_client.mode()
    print(f"{len(looks)} reference looks seeded (M1 {mode}, store {store}, version {looks[0].version})")
    for lk in looks:
        print(f"  {lk.id:20s} {lk.family:12s} primary={lk.primary!s:5s} {lk.image_url}")


if __name__ == "__main__":
    asyncio.run(main())
