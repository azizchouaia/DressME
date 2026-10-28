"""Step 2 — how many new outfits does the piece unlock? (uses M2 with the candidate locked)"""


def count(outfits: list[dict]) -> dict:
    pairs = sorted({i for o in outfits for i in o["items"]})
    return {"new_outfits": len(outfits), "pairs_with": pairs}
