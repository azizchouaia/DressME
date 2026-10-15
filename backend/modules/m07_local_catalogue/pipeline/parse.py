"""Understand a shopping request (FR/EN/Tunisian): category, colour, gender, budget, city + an English prompt.

Rule-based on purpose: same keyword lists as the catalogue cleaning, so "baskets" in a query and
"Baskets" in a product name always land on the same subcategory. FashionCLIP only understands
English, so the visual search uses a prompt rebuilt from the parsed slots ("a photo of white sneakers").
Darija words ("sabbat ahmar") are first turned into French (darija.py).
"""

import difflib
import re

from .. import darija
from ..contract import ParsedQuery
from ..scraper.normalize import CATEGORY_RULES, COLOR_RULES, categorize, color_from_text, fold
from ..taxonomy import (
    ACCESSORY_RULES,
    COLOR_CODES,
    COLOR_EN_PROMPT,
    GOVERNORATES,
    SUBCATEGORIES,
    city_from_text,
    color_code_from_text,
    gender_from_text,
    subcategory_from_text,
)
from ..taxonomy import governorate as governorate_of
from .retrieve import tokenize

_NUM = r"(\d+(?:[.,]\d+)?)"
# "alf" (thousand millimes) is how a dinar is often said in Tunisia: "80 alf" = 80 TND.
_CURRENCY = r"(?:tnd|dt|dinars?|d\.?t\.?|د\.?ت|alf|الف)"
_BETWEEN = re.compile(rf"\bentre\s+{_NUM}\s*(?:{_CURRENCY})?\s+et\s+{_NUM}|\bbetween\s+{_NUM}\s+and\s+{_NUM}")
_MAX = re.compile(
    rf"(?:moins de|max(?:imum)?|budget(?: de| max)?|sous|under|below|less than|jusqu'?a|pas plus de|<=?)"
    rf"\s*:?\s*{_NUM}"
)
_PRICE = re.compile(rf"{_NUM}\s*{_CURRENCY}\b")

# Generic words name a whole category, not one subcategory ("chaussures blanches" = any shoes).
_GENERIC = [
    (re.compile(r"\b(?:chaussures?|shoes?|souliers?)\b"), "shoes"),
    (re.compile(r"\baccessoires?\b"), "accessory"),
    (re.compile(r"\b(?:tenue traditionnelle|traditionnel(?:le)?s?)\b"), "traditional"),
]

SUBCATEGORY_EN = {
    "sneakers": "sneakers",
    "shoes": "shoes",
    "sandals": "sandals",
    "boots": "boots",
    "heels": "high heels",
    "bag": "handbag",
    "accessory": "fashion accessory",
    "hijab": "hijab headscarf",
    "dress": "dress",
    "jumpsuit": "jumpsuit",
    "set": "matching two-piece set",
    "swimwear": "swimsuit",
    "skirt": "skirt",
    "shorts": "shorts",
    "jeans": "jeans",
    "trousers": "trousers",
    "coat": "coat",
    "jacket": "jacket",
    "sweater": "sweater",
    "tshirt": "t-shirt",
    "shirt": "shirt",
    "lingerie": "lingerie",
    "traditional": "traditional tunisian outfit",
    "belt": "belt",
    "jewelry": "jewelry",
    "hat": "hat",
    "socks": "socks",
    "scarf": "scarf",
    "sunglasses": "sunglasses",
    "wallet": "wallet",
    "watch": "watch",
    "hair": "hair accessory",
    "suit": "suit",
    "necklace": "necklace",
    "bracelet": "bracelet",
    "ring": "ring",
    "earrings": "earrings",
}
CATEGORY_EN = {
    "top": "top",
    "bottom": "trousers",
    "dress": "dress",
    "outerwear": "jacket",
    "shoes": "shoes",
    "accessory": "fashion accessory",
    "traditional": "traditional tunisian outfit",
}
# Attributes FashionCLIP knows well, translated from French.
_ATTRIBUTES_EN = [
    (r"lin", "linen"),
    (r"cuir", "leather"),
    (r"daim", "suede"),
    (r"laine", "wool"),
    (r"soie", "silk"),
    (r"satin(?:e)?", "satin"),
    (r"dentelle", "lace"),
    (r"coton", "cotton"),
    (r"velours", "velvet"),
    (r"denim|jean", "denim"),
    (r"imprimee?s?", "printed"),
    (r"fleurie?s?", "floral"),
    (r"rayee?s?", "striped"),
    (r"carreaux", "checked"),
    (r"brodee?s?", "embroidered"),
    (r"plissee?s?", "pleated"),
    (r"longue?s?", "long"),
    (r"courte?s?", "short"),
    (r"oversized?", "oversized"),
    (r"habillee?s?|chic|elegante?s?", "elegant"),
    (r"sport(?:if|ive)?s?", "sporty"),
    (r"plateforme", "platform"),
    (r"talons?", "heeled"),
    (r"slim", "slim"),
    (r"larges?", "wide"),
    (r"mini", "mini"),
    (r"midi", "midi"),
    (r"maxi", "maxi"),
    (r"col v", "v-neck"),
    (r"manches longues", "long sleeve"),
    (r"sans manches", "sleeveless"),
    (r"modeste?s?", "modest"),
    (r"soiree|mariage|ceremonie|gala", "evening"),
]
_ATTRIBUTE_RES = [(re.compile(rf"\b(?:{p})\b"), en) for p, en in _ATTRIBUTES_EN]

# Words that say where/how to buy, not what: kept out of the BM25 terms.
_REQUEST_WORDS = set(
    "je cherche veux voudrais trouve trouver acheter ou boutique boutiques magasin magasins pas cher chere "
    "prix budget moins max maximum sous entre et pour avec une un des les la le du de a au aux en dans sur "
    "tnd dt dinar dinars i want looking find buy where shop shops store under below less than for with the "
    "in some any please svp stp mon ma mes moi me style quelque chose "
    # darija: I want, I am looking for, is there, where, for, in
    "nheb n7eb nhab nlawej nlawwej fama famma win chnowa chnoua brabi lel fi".split()
)
_REQUEST_TOKENS = _REQUEST_WORDS | {t for w in _REQUEST_WORDS for t in tokenize(w)}


def _number(text: str) -> float:
    return float(text.replace(",", "."))


def parse_price(folded: str) -> tuple[float | None, float | None]:
    """(min, max) budget in TND from text, e.g. 'moins de 80 dt' -> (None, 80)."""
    if m := _BETWEEN.search(folded):
        low, high = [_number(g) for g in m.groups() if g]
        return min(low, high), max(low, high)
    if m := _MAX.search(folded):
        return None, _number(m.group(1))
    if m := _PRICE.search(folded):  # a bare "80 dt" in a shopping request is a budget
        return None, _number(m.group(1))
    return None, None


def normalize_color(value: str | None) -> str | None:
    """Accept a colour code ('white') or a colour word in any supported language ('blanc')."""
    if not value:
        return None
    value = value.strip().lower()
    return value if value in COLOR_CODES else color_code_from_text(value)


# Who the piece is for, in the request: the product words plus "for my husband / wife".
_FOR_MEN = re.compile(
    r"\b(?:mon|my) (?:mari|epoux|copain|frere|pere|fiance|husband|boyfriend|brother|father)\b|\bpapa\b"
)
_FOR_WOMEN = re.compile(
    r"\b(?:mon|ma|my) (?:epouse|copine|soeur|mere|fiancee|wife|girlfriend|sister|mother)\b|\bmaman\b"
)
_GENDER_EN = {"women": "women's", "men": "men's"}
# Gender words are a filter, not BM25 terms: a piece estimated "men" from its photo has no "homme" in it.
_GENDER_TOKENS = set(
    tokenize(
        "homme hommes femme femmes men man mens women woman womens dame dames fille filles mixte unisexe"
    )
)


def gender_from_query(folded: str) -> str | None:
    """'chemise homme' / 'pour mon mari' -> 'men'; nothing said -> None."""
    found = gender_from_text(folded)
    if not found:
        men, women = bool(_FOR_MEN.search(folded)), bool(_FOR_WOMEN.search(folded))
        found = "men" if men and not women else "women" if women and not men else ""
    return found or None


def build_prompt(parsed: ParsedQuery, text: str = "") -> str | None:
    """English FashionCLIP prompt from the parsed slots + attributes found in the text."""
    attributes = [en for rx, en in _ATTRIBUTE_RES if rx.search(fold(text))]
    noun = SUBCATEGORY_EN.get(parsed.subcategory or "") or CATEGORY_EN.get(parsed.category or "")
    if not (noun or parsed.color or attributes):
        return None
    words = [
        _GENDER_EN.get(parsed.gender or "", ""),
        COLOR_EN_PROMPT[parsed.color] if parsed.color else "",
        *attributes,
        noun or "clothing item",
    ]
    return "a photo of " + " ".join(w for w in words if w)


def _pattern_words(pattern: str) -> set[str]:
    words = set(re.findall(r"[a-z]{3,}", fold(pattern)))
    return words | {w[:-1] for w in words if w.endswith(("s", "x"))}


# Words the parser knows (category, accessory, colour, attribute keywords + cities): typos are
# corrected towards them and towards the words of the catalogue (see Catalogue.vocabulary).
KEYWORDS: set[str] = (
    set().union(*(_pattern_words(p) for _, p in CATEGORY_RULES))
    | set().union(*(_pattern_words(p) for _, _, p in ACCESSORY_RULES))
    | set().union(*(_pattern_words(p) for _, p in COLOR_RULES))
    | set().union(*(_pattern_words(p) for p, _ in _ATTRIBUTES_EN))
    | {w for city in GOVERNORATES for w in re.findall(r"\w+", fold(city))}
    | {w for french in darija.DARIJA for w in re.findall(r"[a-z]{3,}", fold(french))}
)
_KEYWORDS_SORTED = sorted(KEYWORDS)


def correct_typos(text: str, vocabulary: set[str]) -> str | None:
    """'colier' -> 'collier' when a word is unknown but very close to a known one; None if nothing changed.

    Parser keywords come first: a shop may itself write "colier", which must not make the typo valid.
    Words the rules already understand ("noires", "dorée") are never touched.
    """
    known = sorted(vocabulary)
    changed = False

    def fix(m: re.Match) -> str:
        nonlocal changed
        word = fold(m.group(0))
        if len(word) < 4 or word.isdigit() or word in _REQUEST_TOKENS or word in KEYWORDS:
            return m.group(0)
        if categorize(word) or color_from_text(word) or city_from_text(word):
            return m.group(0)
        close = difflib.get_close_matches(word, _KEYWORDS_SORTED, n=1, cutoff=0.84)
        if not close and word in vocabulary:
            return m.group(0)
        close = close or difflib.get_close_matches(word, known, n=1, cutoff=0.84)
        if not close:
            return m.group(0)
        changed = True
        return close[0]

    corrected = re.sub(r"\w+", fix, text)
    return corrected if changed else None


def parse(query: str, gap: str | None = None, vocabulary: set[str] | None = None) -> ParsedQuery:
    text = " ".join(t for t in (query, gap) if t)
    translated = darija.translate(text)
    if translated:
        text = translated
    corrected = correct_typos(text, vocabulary) if vocabulary else None
    if corrected:
        text = corrected
    folded = fold(text)

    min_price, max_price = parse_price(folded)
    gender = gender_from_query(folded)
    city = city_from_text(text)
    color = color_code_from_text(text)

    category = subcategory = None
    for rx, generic_category in _GENERIC:
        if rx.search(folded):
            category = generic_category
    found = subcategory_from_text(text)
    if found and not (category and SUBCATEGORIES[found][0] == category and found in ("shoes", "accessory")):
        subcategory = found
        category = SUBCATEGORIES[found][0]

    denim = re.search(r"\b(?:jeans?|denim)\b", folded)
    if color == "blue" and denim and not re.search(r"\bbleue?s?\b|\bblue\b", folded):
        color = None  # "jean" alone is a fabric here, not a colour request

    terms = [
        t for t in tokenize(text) if t not in _REQUEST_TOKENS and t not in _GENDER_TOKENS and not t.isdigit()
    ]
    if city:
        terms = [t for t in terms if t not in tokenize(city)]
    parsed = ParsedQuery(
        category=category,
        subcategory=subcategory,
        color=color,
        gender=gender,
        max_price_tnd=max_price,
        min_price_tnd=min_price,
        city=city,
        governorate=governorate_of(city) if city else None,
        terms=terms,
        translated=translated,
        corrected=corrected,
    )
    parsed.prompt_en = build_prompt(parsed, text)
    return parsed
