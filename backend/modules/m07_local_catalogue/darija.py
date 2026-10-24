"""Tunisian darija -> French, so the parser understands "sabbat ahmar" like "chaussures rouge".

Requests are often written in darija, in Latin letters with digits for Arabic sounds ("a7mar",
"5adhra", "9ahwi", "3ers") or in Arabic script ("صباط أحمر"). Each darija word is replaced by the
French word that the category / colour / price rules already know, before typo correction, so the
rest of the pipeline (filters, BM25, FashionCLIP prompt) is unchanged.

Only words with one clear meaning in a shopping request are listed: "jupe" has no entry because its
darija spellings are too close to "jebba".
"""

import re

from .scraper.normalize import fold

# French word -> darija spellings (Latin letters and Arabic script).
DARIJA: dict[str, list[str]] = {
    # pieces
    "chaussures": ["sabbat", "sebbat", "sabbet", "sbabet", "sbabat", "صباط", "صبابط", "حذاء", "أحذية"],
    "baskets": ["sbadri", "sbedri", "sbadria", "sbadriyat", "سبادري", "سبدري"],
    "claquettes": ["chlaka", "chleka", "chlakat", "chlek", "شلاكة", "شلاكات", "شلاك"],
    "chemise": ["sorya", "souriya", "sourya", "souria", "sorria", "سورية", "قميص", "قمصان"],
    "t-shirt": ["maryoul", "mariyoul", "maryoula", "mrayel", "مريول", "مرايل"],
    "pantalon": ["sarwel", "serwel", "sirwel", "sarwal", "srawel", "سروال", "سراول"],
    "manteau": ["kabbout", "kabout", "kabbot", "كبوط", "معطف", "معاطف"],
    "veste": ["jakita", "jaketa", "jakta", "جاكيتة", "جاكيت", "سترة"],
    "robe": ["robba", "rouba", "fostan", "fustan", "روبة", "فستان", "فساتين"],
    "sac": ["chkara", "shkara", "شكارة", "حقيبة", "حقائب"],
    # Arabic script only: the Latin darija spellings of "jupe" are too close to "jebba" (see above)
    "jupe": ["تنورة", "تنانير"],
    "casquette": ["kaskita", "kasketa", "كاسكيطة", "كاسكات"],
    "bonnet": ["ta9ia", "tagia", "takia", "طاقية"],
    "chaussettes": ["t9achir", "tqachir", "tkachir", "تقاشر", "تقاشير"],
    "foulard": ["mahrma", "ma7rma", "mahrama", "محرمة"],
    "ceinture": ["7zem", "hzem", "hzam", "7zam", "حزام"],
    "montre": ["sa3a", "montra", "مونترة", "ساعة"],
    "boucles d'oreilles": ["mengouch", "mangouch", "mnagech", "mnegech", "منقوش", "منڨوش", "مناقش"],
    "bague": ["khatem", "5atem", "debla", "خاتم", "دبلة"],
    "collier": ["sensla", "snesel", "sensela", "سنسلة", "سناسل"],
    "bracelet": ["dbalej", "dbelej", "dbloj", "دبلج", "دبلوج"],
    "lunettes": ["nadhara", "ndhader", "nadhader", "nadharat", "نظارة", "نظارات"],
    "maillot de bain": ["mayou", "مايو"],
    # colours
    "rouge": ["ahmar", "a7mar", "ahmer", "a7mer", "hamra", "7amra", "أحمر", "حمراء", "حمرا"],
    "noir": [
        "akhal",
        "ak7al",
        "ak7el",
        "akhel",
        "kahla",
        "k7ala",
        "k7al",
        "kahel",
        "aswad",
        "souda",
        "أكحل",
        "كحلة",
        "كحلا",
        "أسود",
        "سوداء",
        "سودا",
    ],
    "blanc": [
        "abyadh",
        "abyedh",
        "abiadh",
        "abyad",
        "byadh",
        "bidha",
        "baydha",
        "beydha",
        "bayda",
        "أبيض",
        "بيضاء",
        "بيضا",
    ],
    "bleu": ["azra9", "azre9", "azreg", "azrag", "azraq", "zar9a", "zarga", "zarqa", "أزرق", "زرقاء", "زرقا"],
    "vert": [
        "akhdhar",
        "akhdher",
        "a5dhar",
        "a5dher",
        "akhdar",
        "khadhra",
        "5adhra",
        "khadra",
        "أخضر",
        "خضراء",
        "خضرا",
    ],
    "jaune": ["asfar", "asfer", "safra", "أصفر", "صفراء", "صفرا"],
    # adjectives in -i take -ia / -ية with a feminine noun ("sensla dhahbia", "سنسلة ذهبية")
    "gris": ["rmedi", "rmadi", "ramadi", "rmedia", "fadhi", "fadhia", "رمادي", "رمادية", "فضي", "فضية"],
    "rose": ["wardi", "wardia", "وردي", "وردية"],
    "violet": ["bnafsaji", "banafsaji", "bnafsajia", "بنفسجي", "بنفسجية"],
    "marron": ["9ahwi", "qahwi", "kahwi", "9ahwia", "bonni", "قهوي", "قهوية", "بني", "بنية"],
    "dore": ["dhahbi", "dahbi", "thahbi", "dhahbia", "dhahbiya", "ذهبي", "ذهبية"],
    "orange": ["bortkali", "bourtou9ali", "برتقالي", "برتقالية"],
    # who it is for
    "homme": ["rajel", "rajl", "rjel", "rjal", "rjeli", "رجل", "رجال", "رجالي", "رجالية"],
    "femme": [
        "mra",
        "mraa",
        "nsa",
        "nse",
        "bnet",
        "bnat",
        "sbaya",
        "مرا",
        "مرأة",
        "امرأة",
        "نساء",
        "نسا",
        "نسائي",
        "نسائية",
        "بنات",
    ],
    # occasion, budget
    "mariage": ["3ers", "3rass", "a3ras", "عرس", "أعراس"],
    "soiree": ["sahria", "sahriya", "سهرية"],
    "aid": ["3id", "عيد"],
    "moins de": ["a9al men", "a9al mel", "a9al min", "akal men", "aqal min", "أقل من"],
    "pas cher": ["rkhis", "r5is", "rkhisa", "رخيص"],
}

# Arabic words often carry the article or a preposition: "الأحمر", "بالأحمر", "للرجال".
_ARABIC_PREFIX = r"(?:ال|بال|لل|وال|و|ب|ل)?"
_ARABIC = re.compile(r"[؀-ۿ]")


def _alternative(word: str) -> str:
    word = re.escape(fold(word))
    return _ARABIC_PREFIX + word if _ARABIC.search(word) else word


# Longest spellings first, so "a9al men" wins over a shorter overlapping word.
_SPELLINGS = sorted(((fold(w), fr) for fr, words in DARIJA.items() for w in words), key=lambda x: -len(x[0]))
_FRENCH_OF = {}
for _spelling, _fr in _SPELLINGS:
    _FRENCH_OF.setdefault(_spelling, _fr)
_DARIJA_RE = re.compile(r"(?<!\w)(" + "|".join(_alternative(w) for w, _ in _SPELLINGS) + r")(?!\w)")
_PREFIX_RE = re.compile("^" + _ARABIC_PREFIX)


def translate(text: str) -> str | None:
    """Text with every darija word replaced by its French equivalent; None when there was none."""
    folded = fold(text)

    def french(m: re.Match) -> str:
        word = m.group(1)
        if word in _FRENCH_OF:
            return _FRENCH_OF[word]
        return _FRENCH_OF.get(_PREFIX_RE.sub("", word, count=1), word)

    translated = _DARIJA_RE.sub(french, folded)
    return translated if translated != folded else None
