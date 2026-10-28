"""Normalise raw shop data (categories, colours, sizes, origin) to the M7 catalogue vocabulary."""

import html
import re
import unicodedata


def fold(text: str) -> str:
    """Lowercase, strip accents and HTML so keyword rules work on FR/EN/Tunisian spellings."""
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    # Drop accents but keep non-Latin letters (Arabic product names are common on Tunisian shops).
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    text = text.replace("’", "'").replace(
        "‘", "'"
    )  # "Boucles d’oreilles" written with a typographic apostrophe
    return re.sub(r"\s+", " ", text.lower()).strip()


def clean_text(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()


# Order matters: the first matching rule wins, so specific pieces come before generic ones
# ("veste en jean" -> Veste, "short en jean" -> Short, "jean" -> Jean).
CATEGORY_RULES: list[tuple[str, str]] = [
    # Before shoes and jeans: "chaussettes pour sneakers", "portefeuille ... jean et similicuir"
    (
        "Accessoire",
        r"chaussettes?|socquettes?|socks?|portefeuilles?|porte[- ]feuilles?|porte[- ]cartes?|wallets?",
    ),
    (
        "Traditionnel",
        r"jebba|jbba|jebbet|kaftan|caftan|takchita|jelbeb|jellaba|djellaba|abaya|kachabia|"
        r"sefsari|blouza|keswa|gandoura|qamis|kamis|jalabiya|burnous|kadroun|tabdila|"
        r"tenues? traditionnelles?|"
        r"جلباب|جبة|جبه|قفطان|عباية|عباءة|كاشابية|بلوزة|سفساري|قندورة|برنس",
    ),
    ("Hijab", r"hijab|khimar|jilbab|turban|sous[- ]hijab|bonnet hijab|niqab"),
    (
        "Sneakers",
        # "basket" alone is a sneaker; "short basket", "maillot de basket" are basketball clothes
        r"sneakers?|(?<!short )(?<!shorts )(?<!maillot )(?<!de )(?<!ballon )baskets?(?![ -]?ball)|"
        r"running|air ?force|air ?max|jordan|trainers?|samba|spezial|gazelle|superstar|"
        r"stan ?smith|campus|forum \d+|dunks?|yeezy|speedcat|old ?skool|chuck taylor|all ?star|gel-\w+|"
        r"new balance \d+|mc ?queen",
    ),
    ("Sandales", r"sandales?|sandals?|claquettes?|mules?|tongs?|espadrilles?|slides?|nu[- ]pieds?"),
    ("Bottes", r"bottes?|bottines?|boots?|santiags?"),
    ("Escarpins", r"escarpins?|talons?|heels?|pumps?"),
    (
        "Chaussures",
        r"chaussures?|mocassins?|derbys?|derbies|sabots?|ballerines?|richelieus?|shoes?|loafers?|souliers?|pantoufles?|chaussons?",
    ),
    (
        "Sac",
        r"sacs?|pochettes?|cabas|couffins?|tote ?bags?|bags?|sacoches?|cartables?|besaces?|bananes?|"
        r"backpacks?|clutch|handbags?|purses?|crossbody",
    ),
    ("Robe", r"robes?|dress(es)?|فستان"),
    ("Jupe", r"jupes?|skirts?"),
    ("Combinaison", r"combinaisons?|jumpsuits?|salopettes?|combishort"),
    # Suits: "pantalon de costume" / "veste de costume" stay trousers / jackets (rules below).
    ("Costume", r"(?<!pantalon de )(?<!veste de )(?<!gilet de )(?:costumes?|tailleurs?|smokings?)"),
    (
        "Ensemble",
        r"ensembles?|co-?ords?|survetements?|tracksuits?|suits?|twin ?set|set(?!\s+(?:de|of|d'|\d))",
    ),
    ("Maillot de bain", r"maillots? de bain|bikinis?|burkini|swimsuits?|swimwear"),
    (
        "Lingerie & nuit",
        r"pyjamas?|nuisettes?|lingerie|soutien[- ]gorge|culottes?|boxers?|slips?|"
        r"sous[- ]vetements?|brassieres?|peignoirs?|homewear|calecons?",
    ),
    ("Manteau", r"manteaux?|manteau|trench|doudounes?|parkas?|caban|coats?|puffer"),
    (
        "Veste",
        r"vestes?|blousons?|blazers?|perfectos?|surchemises?|bombers?|jackets?|windbreakers?|coupe-vent|kimonos?|gilets?|gillets?|cardigans?|overshirt",
    ),
    (
        "Pull",
        r"pulls?|puls?|pullovers?|sweats?|sweat-?shirts?|hoodies?|tricots?|sweaters?|cols? roul[e]s?",
    ),
    (
        "T-shirt & top",
        r"t-?shirts?|t-loose|t-classic|maillots? de (?:basket|foot|sport)|jerseys?|tee-?shirts?|tees?|"
        r"polos?|debardeurs?|tops?|bodys?|crop|camisoles?|caracos?|tank|hauts?(?! de gamme)",
    ),
    ("Chemise", r"chemises?|chemisiers?|blouses?|liquettes?|tuniques?|shirts?"),
    ("Short", r"shorts?|bermudas?"),
    ("Jean", r"jeans?|denims?|dengri"),  # dengri: Tunisian word for jeans
    (
        "Pantalon",
        r"pantalons?|joggers?|joggings?|jokings?|leggings?|chinos?|cargos?|palazzos?|pants?|sweatpants|trousers?|jeggings?",
    ),
    (
        "Accessoire",
        r"ceintures?|casquettes?|chapeaux?|chapeau|bonnets?|echarpes?|foulards?|bijoux|bijou|colliers?|coliers?|"
        r"manchettes?|"
        r"bracelets?|boucles? d'oreilles?|puces? d'oreilles?|bagues?|montres?|lunettes?|montures?|berets?|"
        r"parures?|portefeuilles?|porte[- ]feuilles?|"
        r"porte[- ]cartes?|chaussettes?|gants?|cravates?|accessoires?|barrettes?|chouchous?|pinces?|"
        r"bandeaux?|snoods?|chales?|etoles?|belts?|caps?|hats?|socks?|scarf|scarves|jewelry|earrings?|"
        r"necklaces?|rings?|watch(es)?|sunglasses|wallets?|cuff|broches?",
    ),
]
_CATEGORY_RES = [(name, re.compile(rf"\b(?:{pattern})\b")) for name, pattern in CATEGORY_RULES]

# Items that are not fashion pieces (sold by some of the shops) or are for children/babies.
NON_FASHION = re.compile(
    r"\b(?:tasbih|livres?|coran|hadiths?|parfums?|musc|encens|tapis|cosmetiques?|cremes?|savons?|bougies?|"
    r"decorations?|cuisine|creatine|whey|proteines?|gourde|coffret cadeau|carte cadeau|gift ?card|"
    r"emballage|packaging|mug|serviettes?|draps?|coussins?|parure de lit|jouets?|valises?|"
    # home decor and stationery sold by artisan marketplaces (Iley'com, Hraier, Patrinova...)
    r"bougeoirs?|vases?|tasses?|assiettes?|plateaux?|porte[- ]manteaux?|carnets?|cahiers?|"
    r"stickers?|autocollants?|magnets?|poteries?|lampes?|lanternes?|photophores?|sous[- ]verres?|"
    r"dessous d'?assiettes?|boites? a bijoux|figurines?|tableaux?|"
    # furniture and home objects (not "bateau": "col bateau" is a neckline; not "telephone": phone pouches)
    r"consoles?|chaises?|tabourets?|etageres?|meubles?|abat[- ]?jours?|abajours?|portemanteaux?|"
    r"porte[- ]bouteilles?|support plante|mortiers?|cuilleres?|fourchettes?|spatules?|"
    r"corbeilles? artisanales?|coffrets? de maquillage|coffres?|pots? (?:en )?ceramique|cache[- ]pots?|"
    r"pour un sommeil|"
    r"paniers?(?: de)? rangement|sculptures?|statuettes?|art mural|art abstrait|oeuvres?|œuvres?|"
    r"suspension murale|montres? murales?|horloges?|haut[- ]parleurs?|standard telephonique|"
    r"centre (?:de )?table|sous[- ]?plats?|pots? a miel|misbaha|dressage de table|maquettes?|"
    r"modeles? de bateau|(?:ensembles?|elements?|objets?|boites?) decorati\w*|"
    # food (not "chocolat", "miel", "beurre": shops use them as colour names)
    r"cakes?|kaak|gateaux?|petits? fours|biscuits?|patisseries?|confitures?|huile d'?olive|zbib|"
    r"makroudh?|baklawa|bsissa)\b"
)
# Not fashion unless the name also names a piece: "Porte clé" goes, "Ceinture et porte clé" stays.
# "Sac avec charm décoratif", "soutien-gorge corbeille", "boucles effet miroir" are pieces: these words
# only exclude a product whose name names no piece ("Cœur décoratif", "Miroir soleil en rotin").
WEAK_NON_FASHION = re.compile(
    r"\b(?:porte[- ]?cles?|cadres?|tortues?|paniers?|decorati\w*|corbeilles?|miroirs?)\b"
)
KIDS = re.compile(
    r"\b(?:bebes?|baby|babies|enfants?|kids?|junior|fillettes?|garcons?|garconnets?|premiers? pas|layette|"
    r"naissance|nourrissons?|"
    r"\d{1,2} ?(?:-|a) ?\d{1,2} ?ans|\d{1,2} ?ans|toddler|ado|adolescents?)\b"
)


def categorize(*texts: str) -> str | None:
    """Return the first category matched, trying each text in priority order (title first)."""
    for text in texts:
        folded = fold(text)
        if not folded:
            continue
        for name, rx in _CATEGORY_RES:
            if rx.search(folded):
                return name
    return None


def is_non_fashion(*texts: str) -> bool:
    return any(
        NON_FASHION.search(fold(t)) or (WEAK_NON_FASHION.search(fold(t)) and categorize(t) is None)
        for t in texts
        if t
    )


def is_kids(*texts: str) -> bool:
    return any(KIDS.search(fold(t)) for t in texts if t)


# Canonical French colour names (as in the M7 spec, e.g. "Blanc").
COLOR_RULES: list[tuple[str, str]] = [
    ("Bleu marine", r"bleu marine|marine|navy"),
    ("Bleu ciel", r"bleu ciel|ciel|sky ?blue|baby ?blue|light ?blue"),
    ("Bordeaux", r"bordeaux|burgundy|grenat|lie de vin|wine"),
    ("Kaki", r"kaki|khaki|olive|militaire"),
    ("Camel", r"camel|caramel|cognac"),
    ("Beige", r"beige|sable|nude|ecru|creme|cream|ivoire|ivory|off ?white|taupe|sand|stone"),
    ("Noir", r"noire?s?|black"),
    ("Blanc", r"blanc(?:he)?s?|white|wht"),
    ("Gris", r"grise?s?|grey|gray|anthracite|chine|charcoal|argente?e?s?|silver"),
    ("Marron", r"marron|brown|chocolat|moka|mocha|brun|tabac|cafe|coffee"),
    ("Bleu", r"bleue?s?|blue|indigo|turquoise|royal|petrole|cobalt"),
    ("Rouge", r"rouges?|red|carmin|cerise"),
    ("Rose", r"roses?|pink|fuchsia|fushia|framboise|poudre|blush|saumon|salmon|corail|coral"),
    ("Violet", r"violete?s?|purple|mauve|lilas|lavande|lavender|prune|aubergine|lilac|parme"),
    ("Vert", r"verte?s?|green|emeraude|emerald|menthe|mint|sapin|vert d'eau|bouteille"),
    ("Jaune", r"jaunes?|yellow|moutarde|mustard|citron|lemon"),
    ("Orange", r"orange|brique|rouille|terracotta|rust"),
    ("Doré", r"dore[e]?s?|gold|golden"),
    (
        "Multicolore",
        r"multicolore|multi ?color|multi|imprime[e]?s?|print|fleuri|motifs?|rayee?s?|carreaux|"
        r"leopard|camouflage",
    ),
]
_COLOR_WORD_RES = [(name, re.compile(rf"\b(?:{pattern})\b")) for name, pattern in COLOR_RULES]
# Variant colour names can be codes like "T00849-NOIRDEL": also allow substring matches there
# for unambiguous, long-enough colour words.
_COLOR_SUBSTR = [
    ("Bleu marine", "marine"),
    ("Bleu marine", "navy"),
    ("Bordeaux", "bordeaux"),
    ("Kaki", "kaki"),
    ("Beige", "beige"),
    ("Beige", "ecru"),
    ("Noir", "noir"),
    ("Noir", "black"),
    ("Blanc", "blanc"),
    ("Blanc", "white"),
    ("Gris", "gris"),
    ("Gris", "grey"),
    ("Marron", "marron"),
    ("Marron", "brown"),
    ("Bleu", "bleu"),
    ("Bleu", "blue"),
    ("Rouge", "rouge"),
    ("Rose", "rose"),
    ("Rose", "pink"),
    ("Violet", "violet"),
    ("Vert", "vert"),
    ("Vert", "green"),
    ("Jaune", "jaune"),
    ("Orange", "orange"),
    ("Camel", "camel"),
]


def color_from_text(text: str) -> str | None:
    folded = fold(text)
    for name, rx in _COLOR_WORD_RES:
        if rx.search(folded):
            return name
    return None


def color_from_variant(value: str) -> str | None:
    found = color_from_text(value)
    if found:
        return found
    compact = re.sub(r"[^a-z]", "", fold(value))
    for name, word in _COLOR_SUBSTR:
        if word in compact:
            return name
    return None


_DENIM = re.compile(r"\b(?:jeans?|denims?|dengri)\b")


def main_color(title: str, variant_colors: list[str], extra_text: str = "") -> str:
    """Main colour: colour named in the title, else first variant colour, else blue for a jean/denim piece,
    else colour in tags/description. Denim is only a fallback: a "Jean" in variant NOIR is black."""
    return (
        color_from_text(title)
        or next((c for c in map(color_from_variant, variant_colors) if c), None)
        or ("Bleu" if _DENIM.search(fold(title)) else None)
        or color_from_text(extra_text)
        or ""
    )


def join_sizes(values: list[str]) -> str:
    seen: list[str] = []
    for value in values:
        value = (
            clean_text(str(value))
            .upper()
            .replace("TAILLE", "")
            .replace("POINTURE", "")
            .replace("_", "/")
            .strip(" :")
        )
        if value and value not in ("DEFAULT TITLE", "VAR", "UNIQUE", "TU", "ONE SIZE") and value not in seen:
            seen.append(value)
        elif value in ("UNIQUE", "TU", "ONE SIZE") and "Taille unique" not in seen:
            seen.append("Taille unique")
    return ", ".join(seen)


INTERNATIONAL_BRANDS = re.compile(
    r"\b(?:nike|adidas|puma|new balance|converse|vans|asics|reebok|jordan|skechers|fila|lacoste|"
    r"tommy hilfiger|calvin klein|levi'?s|under armour|the north face|timberland|dr\.? ?martens|"
    r"crocs|birkenstock|guess|zara|mango|h&m|ellesse|kappa|champion|salomon|hoka|on running|"
    r"umbro|diadora|le coq sportif|columbia|steve madden|michael kors|ralph lauren|hugo boss|boss|ugg|"
    r"alexander mcqueen|mc ?queen|balenciaga|gucci|prada|versace|dior|louis vuitton|golden goose|off-white|"
    r"rick owens|maison margiela|yeezy|bershka|pull ?& ?bear|stradivarius|lefties|defacto|lc waikiki|"
    # model names often sold without the brand in the title
    r"air[ -]?forces?|air[ -]?max|dunks?|samba|spezial|gazelle|superstar|stan ?smith|speedcat|chuck taylor|"
    r"all ?star|old ?skool|gel-\w+|campus 00s?|forum (?:low|mid|84)|on cloud\w*|cloudtilt|"
    # sneaker / luxury labels resold by Tunisian sneaker shops; nike/new balance also glued to the model
    r"nike\w*|new ?balance\w*|saucony|amiri|chanel|givenchy|lanvin|valentino|bape|bathing ape|moncler|"
    r"monclr|premiata|numeris|alo (?:runner|yoga)|"
    # watches, jewellery and eyewear labels resold by Tunisian accessory shops
    r"bigotti|casio|rolex|fossil|tissot|swatch|cartier|tag heuer|daniel wellington|seiko|citizen|"
    r"festina|swarovski|pandora|hublot|longines|bvlgari|bulgari|ray[ -]?ban|armani|dkny|kenzo|geox|"
    r"clarks|kickers|ecco|simone perele|triumph|calzedonia|intimissimi|tezenis|etam)\b"
)


def origin_type(default: str, *texts: str) -> str:
    """Shop-level origin, overridden to `international_brand` when the piece is a known foreign brand."""
    if any(INTERNATIONAL_BRANDS.search(fold(t)) for t in texts if t):
        return "international_brand"
    return default
