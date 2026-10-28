"""Common vocabulary of the local catalogue, shared by the cleaning step and the search pipeline.

Categories follow the shared data contract (`shared.schemas.GarmentCategory`) so M7 products and M1
wardrobe items can be compared; `subcategory` is the finer type ("sneakers"), `label_fr` the French
display name. Colours use English codes like the Vision agent (M1) plus the French name and a hex value.
"""

import re

from .scraper.normalize import categorize, color_from_text, fold

# French scraper label -> (contract category, subcategory, French display label).
# "dress" is the one-piece / full-look slot: dresses, jumpsuits, two-piece sets, swimsuits.
TAXONOMY: dict[str, tuple[str, str, str]] = {
    "Sneakers": ("shoes", "sneakers", "Baskets"),
    "Chaussures": ("shoes", "shoes", "Chaussures"),
    "Sandales": ("shoes", "sandals", "Sandales"),
    "Bottes": ("shoes", "boots", "Bottes"),
    "Escarpins": ("shoes", "heels", "Escarpins"),
    "Sac": ("accessory", "bag", "Sacs"),
    "Accessoire": ("accessory", "accessory", "Accessoires"),
    "Hijab": ("accessory", "hijab", "Hijabs"),
    "Robe": ("dress", "dress", "Robes"),
    "Combinaison": ("dress", "jumpsuit", "Combinaisons"),
    "Ensemble": ("dress", "set", "Ensembles"),
    "Costume": ("dress", "suit", "Costumes"),
    "Maillot de bain": ("dress", "swimwear", "Maillots de bain"),
    "Jupe": ("bottom", "skirt", "Jupes"),
    "Short": ("bottom", "shorts", "Shorts"),
    "Jean": ("bottom", "jeans", "Jeans"),
    "Pantalon": ("bottom", "trousers", "Pantalons"),
    "Manteau": ("outerwear", "coat", "Manteaux"),
    "Veste": ("outerwear", "jacket", "Vestes"),
    "Pull": ("top", "sweater", "Pulls & sweats"),
    "T-shirt & top": ("top", "tshirt", "T-shirts & tops"),
    "Chemise": ("top", "shirt", "Chemises"),
    "Lingerie & nuit": ("top", "lingerie", "Lingerie & nuit"),
    "Traditionnel": ("traditional", "traditional", "Tenues traditionnelles"),
}
SUBCATEGORIES = {sub: (cat, label) for cat, sub, label in TAXONOMY.values()}

# Accessories are refined from the product name (searching "ceinture" must not return necklaces).
ACCESSORY_RULES: list[tuple[str, str, str]] = [
    ("belt", "Ceintures", r"ceintures?|belts?"),
    # Jewelry is split by type: a search for "bracelet" must not return rings.
    (
        "earrings",
        "Boucles d'oreilles",
        r"boucles? d'oreilles?|puces? d'oreilles?|clous? d'oreilles?|earrings?|creoles?",
    ),
    (
        "necklace",
        "Colliers",
        r"colliers?|coliers?|pendentifs?|chaines?|chaine|sautoirs?|necklaces?|pendants?",
    ),
    ("bracelet", "Bracelets", r"bracelets?|gourmettes?|joncs?|bangles?|cuff|manchettes?"),
    ("ring", "Bagues", r"bagues?|rings?|alliances?|chevalieres?"),
    ("jewelry", "Bijoux", r"bijoux|bijou|broches?|parures?|jewelry"),
    ("hat", "Chapeaux & casquettes", r"casquettes?|chapeaux?|chapeau|bonnets?|caps?|hats?|beret"),
    ("socks", "Chaussettes", r"chaussettes?|socquettes?|socks?"),
    ("scarf", "Écharpes & foulards", r"echarpes?|foulards?|chales?|etoles?|snoods?|scarf|scarves"),
    ("sunglasses", "Lunettes", r"lunettes?|montures?|sunglasses"),
    ("wallet", "Portefeuilles", r"portefeuilles?|porte[- ]feuilles?|porte[- ]cartes?|wallets?"),
    ("watch", "Montres", r"montres?|watch(?:es)?"),
    ("hair", "Accessoires cheveux", r"barrettes?|chouchous?|pinces?|bandeaux?|cheveux"),
]
_ACCESSORY_RES = [(sub, label, re.compile(rf"\b(?:{p})\b")) for sub, label, p in ACCESSORY_RULES]
for _sub, _label, _ in ACCESSORY_RULES:
    SUBCATEGORIES[_sub] = ("accessory", _label)


def classify(label: str, product_name: str = "") -> tuple[str, str, str] | None:
    """Scraper label ("Sneakers") -> (category, subcategory, label_fr), refining accessories by name."""
    entry = TAXONOMY.get(label)
    if entry is None:
        return None
    if entry[1] == "accessory":
        folded = fold(product_name)
        for sub, sub_label, rx in _ACCESSORY_RES:
            if rx.search(folded):
                return "accessory", sub, sub_label
    return entry


def subcategory_from_text(text: str) -> str | None:
    """Free text (FR/EN/Tunisian/Arabic) -> subcategory code, e.g. "baskets blanches" -> "sneakers"."""
    label = categorize(text)
    if label is None:
        return None
    found = classify(label, text)
    return found[1] if found else None


# French colour name (scraper output) -> (code, hex). Codes match the Vision agent's colour names.
COLORS: dict[str, tuple[str, str]] = {
    "Noir": ("black", "#000000"),
    "Blanc": ("white", "#FFFFFF"),
    "Gris": ("grey", "#808080"),
    "Beige": ("beige", "#D9C8A9"),
    "Camel": ("camel", "#C19A6B"),
    "Marron": ("brown", "#6F4E37"),
    "Bleu": ("blue", "#2F5DA8"),
    "Bleu marine": ("navy", "#1F2A44"),
    "Bleu ciel": ("light_blue", "#9CC7EA"),
    "Rouge": ("red", "#C0262D"),
    "Bordeaux": ("burgundy", "#7A1F2B"),
    "Rose": ("pink", "#F2A7BB"),
    "Violet": ("purple", "#7B4B94"),
    "Vert": ("green", "#3C7A46"),
    "Kaki": ("khaki", "#6B6B3A"),
    "Jaune": ("yellow", "#F2C230"),
    "Orange": ("orange", "#EE7F2D"),
    "Doré": ("gold", "#C9A646"),
    "Multicolore": ("multicolor", ""),
}
COLOR_CODES = {code: (fr, hex_) for fr, (code, hex_) in COLORS.items()}
COLOR_EN_PROMPT = {code: code.replace("_", " ") for code in COLOR_CODES}


def color_code_from_text(text: str) -> str | None:
    fr = color_from_text(text)
    return COLORS[fr][0] if fr else None


# Gender of a piece: code -> French label. Shops write it in the name or the URL ("Basket femme",
# /collections/homme); pipeline/attributes.py estimates it from the photo when they do not. "" = unknown.
GENDERS = {"women": "Femme", "men": "Homme", "unisex": "Mixte"}
OPPOSITE_GENDER = {"women": "men", "men": "women"}


# English display labels (the app's Espace pro and `language="en"` answers); French stays the default.
SUBCATEGORY_EN = {
    "sneakers": "Sneakers",
    "shoes": "Shoes",
    "sandals": "Sandals",
    "boots": "Boots",
    "heels": "Heels",
    "bag": "Bags",
    "accessory": "Accessories",
    "hijab": "Hijabs",
    "dress": "Dresses",
    "jumpsuit": "Jumpsuits",
    "set": "Sets",
    "suit": "Suits",
    "swimwear": "Swimwear",
    "skirt": "Skirts",
    "shorts": "Shorts",
    "jeans": "Jeans",
    "trousers": "Trousers",
    "coat": "Coats",
    "jacket": "Jackets",
    "sweater": "Sweaters",
    "tshirt": "T-shirts & tops",
    "shirt": "Shirts",
    "lingerie": "Lingerie & nightwear",
    "traditional": "Traditional outfits",
    "belt": "Belts",
    "bracelet": "Bracelets",
    "ring": "Rings",
    "jewelry": "Jewellery",
    "necklace": "Necklaces",
    "earrings": "Earrings",
    "hat": "Hats & caps",
    "socks": "Socks",
    "scarf": "Scarves",
    "sunglasses": "Sunglasses",
    "wallet": "Wallets",
    "watch": "Watches",
    "hair": "Hair accessories",
}
GENDERS_EN = {"women": "Women's", "men": "Men's", "unisex": "Unisex"}
GENDERS_AR = {"women": "نسائي", "men": "رجالي", "unisex": "للجنسين"}
SUBCATEGORY_AR = {
    "sneakers": "أحذية رياضية",
    "shoes": "أحذية",
    "sandals": "صنادل",
    "boots": "جزمات",
    "heels": "أحذية بكعب",
    "bag": "حقائب",
    "accessory": "إكسسوارات",
    "hijab": "حجابات",
    "dress": "فساتين",
    "jumpsuit": "جمبسوت",
    "set": "أطقم",
    "suit": "بدلات",
    "swimwear": "ملابس سباحة",
    "skirt": "تنانير",
    "shorts": "شورتات",
    "jeans": "جينز",
    "trousers": "سراويل",
    "coat": "معاطف",
    "jacket": "سترات",
    "sweater": "كنزات",
    "tshirt": "تيشيرتات",
    "shirt": "قمصان",
    "lingerie": "ملابس داخلية",
    "traditional": "ملابس تقليدية",
    "belt": "أحزمة",
    "bracelet": "أساور",
    "ring": "خواتم",
    "jewelry": "مجوهرات",
    "hat": "قبعات",
    "socks": "جوارب",
    "scarf": "أوشحة",
    "sunglasses": "نظارات شمسية",
    "wallet": "محافظ",
    "watch": "ساعات",
    "hair": "إكسسوارات شعر",
    "necklace": "قلادات",
    "earrings": "أقراط",
}
COLOR_AR = {
    "black": "أسود",
    "white": "أبيض",
    "grey": "رمادي",
    "beige": "بيج",
    "camel": "جملي",
    "brown": "بني",
    "blue": "أزرق",
    "navy": "كحلي",
    "light_blue": "أزرق فاتح",
    "red": "أحمر",
    "burgundy": "عنابي",
    "pink": "وردي",
    "purple": "بنفسجي",
    "green": "أخضر",
    "khaki": "كاكي",
    "yellow": "أصفر",
    "orange": "برتقالي",
    "gold": "ذهبي",
    "multicolor": "متعدد الألوان",
}


# Display labels of the contract categories (a usual budget can be learned for a whole category).
CATEGORY_LABELS = {  # (fr, en, ar)
    "top": ("Hauts", "Tops", "قطع علوية"),
    "bottom": ("Bas", "Bottoms", "قطع سفلية"),
    "dress": ("Robes & ensembles", "Dresses & sets", "فساتين وأطقم"),
    "outerwear": ("Vestes & manteaux", "Jackets & coats", "سترات ومعاطف"),
    "shoes": ("Chaussures", "Shoes", "أحذية"),
    "accessory": ("Accessoires", "Accessories", "إكسسوارات"),
    "traditional": ("Tenues traditionnelles", "Traditional outfits", "ملابس تقليدية"),
}
_LANG = {"fr": 0, "en": 1, "ar": 2}


def label(subcategory: str, language: str = "fr") -> str:
    """Display label of a subcategory (or a category): "Baskets" (fr), "Sneakers" (en), Arabic (ar)."""
    if subcategory not in SUBCATEGORIES and subcategory in CATEGORY_LABELS:
        return CATEGORY_LABELS[subcategory][_LANG.get(language, 0)]
    if language == "en":
        return SUBCATEGORY_EN.get(subcategory, subcategory)
    if language == "ar":
        return SUBCATEGORY_AR.get(subcategory, SUBCATEGORIES[subcategory][1])
    return SUBCATEGORIES[subcategory][1]


# One piece of a wardrobe, singular (FR, EN, AR): "chemise (blanc)" / "white shirt" / "قميص أبيض".
_PIECE = {
    "jeans": ("jean", "jeans", "جينز"),
    "shirt": ("chemise", "shirt", "قميص"),
    "sweater": ("pull", "sweater", "كنزة"),
    "sneakers": ("baskets", "sneakers", "حذاء رياضي"),
    "dress": ("robe", "dress", "فستان"),
    "jacket": ("veste", "jacket", "سترة"),
    "coat": ("manteau", "coat", "معطف"),
    "bag": ("sac", "bag", "حقيبة"),
    "tshirt": ("t-shirt", "t-shirt", "تيشيرت"),
    "trousers": ("pantalon", "trousers", "سروال"),
    "skirt": ("jupe", "skirt", "تنورة"),
    "shorts": ("short", "shorts", "شورت"),
    "sandals": ("sandales", "sandals", "صندل"),
    "heels": ("escarpins", "heels", "حذاء بكعب"),
    "shoes": ("chaussures", "shoes", "حذاء"),
    "boots": ("bottes", "boots", "جزمة"),
    "suit": ("costume", "suit", "بدلة"),
    "set": ("ensemble", "set", "طقم"),
    "traditional": ("tenue traditionnelle", "traditional outfit", "لباس تقليدي"),
    "belt": ("ceinture", "belt", "حزام"),
    "scarf": ("foulard", "scarf", "وشاح"),
    "hijab": ("hijab", "hijab", "حجاب"),
}


def piece_name(subcategory: str | None, colour: str | None, language: str = "fr") -> str:
    """A wardrobe piece in a reason or an outfit: 'chemise (blanc)' (fr), 'white shirt' (en), Arabic."""
    lang = _LANG.get(language, 0)
    names = _PIECE.get(subcategory or "")
    name = names[lang] if names else (label(subcategory, language).lower() if subcategory else "pièce")
    if not colour or colour not in COLOR_CODES:
        return name
    if language == "en":
        return f"{colour_name(colour, 'en')} {name}"
    if language == "ar":
        return f"{name} {colour_name(colour, 'ar')}"
    return f"{name} ({colour_name(colour, 'fr')})"


def colour_name(code: str, language: str = "fr") -> str:
    """ "bleu marine" (fr), "navy blue" (en), "كحلي" (ar), lower case."""
    if language == "en":
        return code.replace("_", " ")
    if language == "ar":
        return COLOR_AR.get(code, code)
    return COLOR_CODES[code][0].lower()


_UNISEX_RE = re.compile(r"\b(?:unisexe?|mixte)\b")
# Garments that are always for one gender here count like the word itself (an abaya, a qamis).
_WOMEN_RE = re.compile(
    r"\b(?:femmes?|woman|women|womens|dames?|filles?|feminine?s?|ladies|lady|abayas?|caftans?|kaftans?"
    r"|takchitas?|burkinis?|nuisettes?|soutien[- ]gorges?)\b"
)
_MEN_RE = re.compile(r"\b(?:hommes?|man|men|mens|masculine?s?|monsieur|qamis+|kamis+)\b")


def gender_from_text(*texts: str) -> str:
    """'Basket femme' -> 'women'; 'unisexe' -> 'unisex'; both genders or none named -> '' (unknown)."""
    folded = " ".join(fold(t) for t in texts if t)
    if _UNISEX_RE.search(folded):
        return "unisex"
    women, men = bool(_WOMEN_RE.search(folded)), bool(_MEN_RE.search(folded))
    if women != men:
        return "women" if women else "men"
    return ""


# City -> governorate. Product cities are where the shop is; a search "à Tunis" matches the whole governorate.
GOVERNORATES: dict[str, str] = {
    "Tunis": "Tunis",
    "La Marsa": "Tunis",
    "Le Bardo": "Tunis",
    "Carthage": "Tunis",
    "Le Kram": "Tunis",
    "La Goulette": "Tunis",
    "Lac": "Tunis",
    "Menzah": "Tunis",
    "Ariana": "Ariana",
    "La Soukra": "Ariana",
    "Ennasr": "Ariana",
    "Raoued": "Ariana",
    "Ben Arous": "Ben Arous",
    "Mégrine": "Ben Arous",
    "El Mourouj": "Ben Arous",
    "Manouba": "Manouba",
    "Bizerte": "Bizerte",
    "Nabeul": "Nabeul",
    "Hammamet": "Nabeul",
    "Kélibia": "Nabeul",
    "Menzel Temime": "Nabeul",
    "Sousse": "Sousse",
    "Monastir": "Monastir",
    "Ksar Hellal": "Monastir",
    "Moknine": "Monastir",
    "Mahdia": "Mahdia",
    "Sfax": "Sfax",
    "Kairouan": "Kairouan",
    "Gabès": "Gabès",
    "Médenine": "Médenine",
    "Djerba": "Médenine",
    "Zarzis": "Médenine",
    "Gafsa": "Gafsa",
    "Béja": "Béja",
    "Jendouba": "Jendouba",
    "Le Kef": "Le Kef",
    "Siliana": "Siliana",
    "Zaghouan": "Zaghouan",
    "Kasserine": "Kasserine",
    "Sidi Bouzid": "Sidi Bouzid",
    "Tozeur": "Tozeur",
    "Kébili": "Kébili",
    "Tataouine": "Tataouine",
}
_CITY_BY_FOLD = {fold(city): city for city in GOVERNORATES} | {
    "marsa": "La Marsa",
    "soukra": "La Soukra",
    "manzel tmim": "Menzel Temime",
    "beja": "Béja",
    "kef": "Le Kef",
    "gabes": "Gabès",
    "medenine": "Médenine",
    "kelibia": "Kélibia",
    "kebili": "Kébili",
    "megrine": "Mégrine",
    "mourouj": "El Mourouj",
    "bardo": "Le Bardo",
}
_CITY_RE = re.compile(
    r"\b(" + "|".join(sorted(map(re.escape, _CITY_BY_FOLD), key=len, reverse=True)) + r")\b"
)


def canonical_city(name: str) -> str | None:
    return _CITY_BY_FOLD.get(fold(name).strip())


def city_from_text(text: str) -> str | None:
    """First Tunisian city named in a free-text query ("baskets à la Marsa" -> "La Marsa")."""
    m = _CITY_RE.search(fold(text))
    return _CITY_BY_FOLD[m.group(1)] if m else None


def governorate(city: str) -> str | None:
    return GOVERNORATES.get(city)
