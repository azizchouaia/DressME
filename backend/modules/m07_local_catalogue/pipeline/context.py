"""Tunisian occasions and seasons in a request (idea 8): "tenue pour un mariage", "3ers", "soirée de Ramadan",
"robe d'été", "pull pour l'hiver", "tenue l b7ar".

Rule-based, like the rest of parse.py: one lexicon in FR / EN / darija / Arabic, matched on fold()ed text.
- An occasion with no piece named ("tenue pour l'Aïd") limits the search to the pieces worn for it.
- A season re-ranks the pieces: names that say summer (lin, débardeur, crochet…) or winter (velours, laine,
  polaire…) and types made for it (sandals, swimwear / coats, boots, sweaters). It never hides a piece.
The occasion codes are French and shared with M14 (hand-off summary, stylist specialities).
"""

import re

# code -> pattern (on fold()ed text), pieces worn for it, FashionCLIP words, English name, and the
# phrase after "pour" / "for" in French and English.
# Order matters: in one sentence the first occasion wins ("robe de soirée pour un mariage" -> mariage).
OCCASIONS: dict[str, dict] = {
    "mariage": {
        "pattern": r"\bmariage\b|\bwedding\b|\b3[eo]rs\b|عرس",
        "pieces": ["dress", "set", "suit", "jumpsuit", "traditional", "heels"],
        "prompt": "elegant wedding guest",
        "en": "wedding",
        "fr": "un mariage",
        "ar": "عرس",
        "for_en": "a wedding",
    },
    "fiançailles": {
        "pattern": r"\bfiancailles\b|\bengagement\b|\bkhotba\b|\b5otba\b|خطوبة",
        "pieces": ["dress", "set", "suit", "jumpsuit", "traditional", "heels"],
        "prompt": "elegant engagement party",
        "en": "engagement",
        "fr": "des fiançailles",
        "ar": "خطوبة",
        "for_en": "an engagement",
    },
    "henna": {
        "pattern": r"\bhenn?a\b|\bhenne\b|\boutia\b|حنة",
        "pieces": ["traditional", "dress", "set"],
        "prompt": "traditional tunisian henna night",
        "en": "henna",
        "fr": "un henné",
        "ar": "حنة",
        "for_en": "a henna night",
    },
    "aïd": {
        "pattern": r"\baid\b|\beid\b|\b3id\b|عيد",
        "pieces": ["traditional", "dress", "set", "suit", "shirt"],
        "prompt": "festive eid",
        "en": "Eid",
        "fr": "l'Aïd",
        "ar": "العيد",
        "for_en": "Eid",
    },
    "ramadan": {
        "pattern": r"\bramadh?an\b|\bramdh?an\b|\bsahri(?:a|ya|yet)\b|\bs7ri(?:a|ya)\b|رمضان|سهرية",
        "pieces": ["traditional", "dress", "set", "jumpsuit", "hijab"],
        "prompt": "modest elegant ramadan evening",
        "en": "Ramadan evening",
        "fr": "les soirées de Ramadan",
        "ar": "سهرات رمضان",
        "for_en": "Ramadan evenings",
    },
    "entretien": {
        "pattern": r"\bentretien\b|\binterview\b",
        "pieces": ["suit", "shirt", "trousers", "jacket", "shoes"],
        "prompt": "formal job interview",
        "en": "job interview",
        "fr": "un entretien",
        "ar": "مقابلة عمل",
        "for_en": "a job interview",
    },
    "soutenance": {
        "pattern": r"\bsoutenance\b|\bgraduation\b",
        "pieces": ["suit", "dress", "shirt", "trousers", "jacket", "heels"],
        "prompt": "formal graduation",
        "en": "graduation",
        "fr": "une soutenance",
        "ar": "مناقشة",
        "for_en": "a graduation",
    },
    "travail": {
        "pattern": r"\bbureau\b|\btravail\b|\boffice\b|\bwork\b",
        "pieces": ["shirt", "trousers", "jacket", "suit", "dress", "shoes"],
        "prompt": "office workwear",
        "en": "work",
        "fr": "le travail",
        "ar": "العمل",
        "for_en": "work",
    },
    "soirée": {
        "pattern": r"\bsoiree\b|\bgala\b|\bparty\b|\bfete\b",
        "pieces": ["dress", "jumpsuit", "set", "suit", "heels"],
        "prompt": "evening party",
        "en": "evening party",
        "fr": "une soirée",
        "ar": "سهرة",
        "for_en": "an evening party",
    },
    "plage": {
        "pattern": r"\bplage\b|\bbeach\b|\bb7ar\b|\bbhar\b|البحر|بحر",
        "pieces": ["swimwear", "shorts", "sandals", "tshirt", "sunglasses", "hat"],
        "prompt": "beach",
        "en": "beach",
        "fr": "la plage",
        "ar": "البحر",
        "for_en": "the beach",
        "season": "summer",
    },
}
_OCCASION_RES = [(code, re.compile(o["pattern"])) for code, o in OCCASIONS.items()]
# Occasions where a casual piece is out of place (a sports jacket at a wedding): every one but the beach.
DRESSY = {code for code in OCCASIONS if code != "plage"}
# A casual piece: its type, or a word of its name (fold()ed).
CASUAL_TYPES = {"sneakers", "swimwear", "shorts", "socks"}
_CASUAL_WORDS = re.compile(
    r"\b(?:sport|sportswear|jogging|joggers?|survetements?|survet|training|running|fitness|gym|hoodies?"
    r"|capuche|pyjamas?|claquettes?|tongs?|plage|beach|cargo)\b"
)


def is_casual(folded_name: str, subcategory: str) -> bool:
    """A sports / beach / home piece, left out of a dressy occasion unless that type is asked for."""
    return subcategory in CASUAL_TYPES or bool(_CASUAL_WORDS.search(folded_name))


# M2 (outfits) knows three contexts: work / casual / event.
M2_OCCASION = {
    "mariage": "event",
    "fiançailles": "event",
    "henna": "event",
    "aïd": "event",
    "ramadan": "event",
    "soirée": "event",
    "soutenance": "event",
    "entretien": "work",
    "travail": "work",
    "plage": "casual",
}

SEASONS: dict[str, dict] = {
    "summer": {
        "pattern": r"\bete\b|\bestivale?s?\b|\bsummer\b|\bsif\b|\bsayf\b|\bchaleur\b|صيف",
        # words of product names (fold()ed) that make a piece a summer one; types made for it
        "words": r"\b(?:lin|linen|leger|legere|bretelles?|debardeur|manches courtes|sans manches|ete|summer|"
        r"plage|beach|crochet|voile|mousseline)\b",
        "types": ["sandals", "swimwear", "shorts", "sunglasses"],
        "pieces": ["dress", "set", "tshirt", "shirt", "shorts", "skirt", "sandals", "swimwear"],
        "prompt": "light summer",
        "en": "summer",
        "fr": "l'été",
        "ar": "الصيف",
    },
    "winter": {
        "pattern": r"\bhiver\b|\bhivernale?s?\b|\bwinter\b|\bchta\b|\bfroid\b|\bcold\b|شتاء|شتا\b|برد",
        "words": r"\b(?:laine|wool|velours|velvet|cachemire|polaire|doudoune|fourree?s?|matelassee?s?|"
        r"manches longues|col roule|teddy|sherpa|hiver|winter|maille|tricot|molleton|parka)\b",
        "types": ["boots", "coat", "sweater", "scarf"],
        "pieces": ["coat", "jacket", "sweater", "boots", "trousers", "jeans"],
        "prompt": "warm winter",
        "en": "winter",
        "fr": "l'hiver",
        "ar": "الشتاء",
    },
}
_SEASON_RES = {code: re.compile(s["pattern"]) for code, s in SEASONS.items()}
_SEASON_WORDS = {code: re.compile(s["words"]) for code, s in SEASONS.items()}
OPPOSITE_SEASON = {"summer": "winter", "winter": "summer"}

# Words of the occasion / season lexicon: not BM25 terms (no product name says "mariage").
CONTEXT_TOKENS = {
    "mariage", "wedding", "fiancailles", "engagement", "henna", "hena", "henne", "aid", "eid", "ramadan",
    "entretien", "interview", "soutenance", "graduation", "soiree", "party", "fete", "plage", "beach",
    "ete", "summer", "hiver", "winter", "froid", "cold", "chaleur", "estivale", "tenue", "tenues",
    "outfit", "outfits", "look", "occasion",
}  # fmt: skip


def occasion_of(folded: str) -> str | None:
    """'tenue pour le 3ers de ma soeur' -> 'mariage'; the first occasion of OCCASIONS wins."""
    return next((code for code, rx in _OCCASION_RES if rx.search(folded)), None)


def season_of(folded: str, occasion: str | None = None) -> str | None:
    """Season said in the request ('été', 'sif', 'شتاء'), else the one of the occasion (plage -> summer)."""
    found = [code for code, rx in _SEASON_RES.items() if rx.search(folded)]
    if len(found) == 1:
        return found[0]
    return OCCASIONS.get(occasion or "", {}).get("season") if not found else None


def season_of_name(folded_name: str) -> str | None:
    """'summer' / 'winter' when the product name alone says it (lin / velours...), else None."""
    summer = bool(_SEASON_WORDS["summer"].search(folded_name))
    winter = bool(_SEASON_WORDS["winter"].search(folded_name))
    return "summer" if summer and not winter else "winter" if winter and not summer else None


def season_hint(folded_name: str, subcategory: str) -> int:
    """+1 a summer piece, -1 a winter piece, 0 neither or both (from its name and its type)."""
    summer = bool(_SEASON_WORDS["summer"].search(folded_name)) or subcategory in SEASONS["summer"]["types"]
    winter = bool(_SEASON_WORDS["winter"].search(folded_name)) or subcategory in SEASONS["winter"]["types"]
    return int(summer) - int(winter)


def pieces_for(occasion: str | None, season: str | None) -> list[str]:
    """Types to search when the request names no piece: those of the occasion, else of the season."""
    if occasion:
        return list(OCCASIONS[occasion]["pieces"])
    return list(SEASONS[season]["pieces"]) if season else []


def prompt_words(occasion: str | None, season: str | None) -> list[str]:
    """English words for the FashionCLIP prompt ('a photo of light summer beach outfit')."""
    words = []
    if season:
        words.append(SEASONS[season]["prompt"])
    if occasion:
        words.append(OCCASIONS[occasion]["prompt"])
    return words


def phrase(code: str, language: str) -> str:
    """How an occasion or a season reads after "pour" / "for" / "لـ": "un mariage", "a wedding", "عرس"."""
    entry = OCCASIONS.get(code) or SEASONS[code]
    key = {"en": "for_en" if code in OCCASIONS else "en", "ar": "ar"}.get(language, "fr")
    return entry[key]
