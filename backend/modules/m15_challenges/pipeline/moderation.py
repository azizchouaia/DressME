"""if/else moderation of post comments: the community feed must stay friendly (BO7 community objective).

Checks, in order: empty / too long, links (spam), shouting, repeated characters, blocked words (en/fr/derja).
Returns (ok, reason). A real classifier can replace it later without changing the API.
"""

import re

MAX_LEN = 280
BLOCKED = {
    # insults and body shaming, in English, French and Tunisian derja (Latin letters); kept short on purpose
    "ugly",
    "fat",
    "stupid",
    "idiot",
    "loser",
    "trash",
    "moche",
    "gros",
    "grosse",
    "nul",
    "nulle",
    "idiote",
    "bete",
    "mekhyeb",
    "m5ayeb",
    "khayeb",
    "5ayeb",
    "mahbel",
    "bhim",
}
LINK = re.compile(r"(https?://|www\.|\.com\b|\.tn\b)", re.I)


def check(text: str) -> tuple[bool, str | None]:
    t = (text or "").strip()
    if not t:
        return False, "the comment is empty"
    if len(t) > MAX_LEN:
        return False, f"keep it under {MAX_LEN} characters"
    if LINK.search(t):
        return False, "links are not allowed in comments"
    letters = [c for c in t if c.isalpha()]
    if len(letters) >= 12 and sum(c.isupper() for c in letters) / len(letters) > 0.8:
        return False, "please do not write in capitals"
    if re.search(r"(.)\1{5,}", t):
        return False, "too many repeated characters"
    words = set(re.findall(r"[a-z0-9]+", t.lower()))
    if words & BLOCKED:
        return False, "be kind: this comment contains a hurtful word"
    return True, None
