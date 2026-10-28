"""Step 3 — does it fill a gap in the wardrobe? (gaps from M5 profile / analytics)

Gap format: "<colour> <type>" ("white shirt"), "<c1>|<c2> <type>" ("navy|black blazer") or "any <type>".
"""


def fill(gaps: list[str], subcategory: str, colour: str) -> str | None:
    for g in gaps:
        words = g.lower().split()
        if len(words) == 1 and words[0] == subcategory.lower():
            return g
        if len(words) >= 2 and words[-1] == subcategory.lower() and (words[0] == "any" or colour.lower() in words[0].split("|")):
            return g
    return None
