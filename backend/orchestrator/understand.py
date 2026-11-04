"""Understands what the user typed before any LLM: typos, French / Tounsi words, the piece, its colour and price.

The assistant must route a jury's real sentences ("shoul i by a blue costume with 320dt", "nechri pull noir
b 80 dinars?") to the right agent every time. An LLM (8B local) is not reliable for that; these rules are.
"""

from __future__ import annotations

import re
import unicodedata

# piece words -> Smart Buy's types (modules/m06_smartbuy/synthetic.TYPES)
TYPE_WORDS = {
    "t-shirt": ["t-shirt", "tshirt", "t shirt", "tee", "tee-shirt", "tricot"],
    "shirt": ["shirt", "chemise", "9amis", "qamis", "kamis"],
    "sweater": ["sweater", "pull", "pullover", "jumper", "hoodie", "sweat", "sweatshirt", "cardigan"],
    "blouse": ["blouse", "top"],
    "jeans": ["jean", "jeans", "denim"],
    "chinos": ["chino", "chinos"],
    "trousers": ["trouser", "trousers", "pants", "pantalon", "serwel", "sarwel"],
    "skirt": ["skirt", "jupe"],
    "sneakers": ["sneaker", "sneakers", "basket", "baskets", "trainers", "espadrille", "sbadri"],
    "loafers": ["loafer", "loafers", "mocassin", "mocassins"],
    "boots": ["boot", "boots", "bottes", "bottines"],
    "sandals": ["sandal", "sandals", "sandale", "sandales", "slippers"],
    "jacket": ["jacket", "veste", "blouson", "jaket", "jakta", "parka", "bomber"],
    "coat": ["coat", "manteau", "trench", "kabbot"],
    "blazer": ["blazer", "costume", "suit", "tailleur", "kostim"],
    "dress": ["dress", "robe", "rouba"],
    "jebba": ["jebba", "jebbah", "jbba"],
}
COLOUR_WORDS = {
    "white": ["white", "blanc", "blanche", "abyedh", "byedh"],
    "black": ["black", "noir", "noire", "akhal", "k7al", "kahla"],
    "grey": ["grey", "gray", "gris", "grise", "rmedi"],
    "navy": ["navy", "marine", "bleu marine", "dark blue"],
    "beige": ["beige", "cream", "creme", "crème", "ecru"],
    "brown": ["brown", "marron", "brun", "chocolat", "9ahwi"],
    "camel": ["camel", "tan"],
    "blue": ["blue", "bleu", "bleue", "azra9", "zar9a", "light blue", "sky"],
    "olive": ["olive", "khaki", "kaki"],
    "red": ["red", "rouge", "ahmer", "hamra"],
    "pink": ["pink", "rose"],
    "green": ["green", "vert", "verte", "akhdher", "khadhra"],
    "burgundy": ["burgundy", "bordeaux", "wine"],
    "mustard": ["mustard", "yellow", "jaune", "moutarde", "asfer"],
}

_BUY = (r"\b(sh?o?u?ld i (buy|by|bye|get|purchase|take)|should i b(uy|y)|buy (it|this|that|a|an|the)|by (it|this|a|an)|"
        r"worth (it|buying|the price)|good (buy|deal|price)|is it a good|acheter|j'?ach[eè]te|je (l'?)?ach[eè]te|"
        r"vaut|ça vaut|nechri|nichri|n?chri|nichrih|nechrih|yest7a9|ya7lili)\b")
_SHOP = (r"\b(find .*(shop|store|boutique|tunis|sfax|sousse|near)|where (can|to|do) (i )?(buy|get|find)|"
         r"in a (shop|store)|local shops?|boutiques?|magasins?|win nal9a|win nlawej|ou (acheter|trouver))\b")
_WEAR = (r"\b(what (should|do|can|shall) i wear|wear (today|tomorrow|tonight)|outfit|tenue|look (for|of) (today|tomorrow)|"
         r"n?elbes|chnowa nelbes|quoi (mettre|porter)|habiller|dress me|another (one|outfit)|une autre|autre tenue|"
         r"change (it|the outfit|the shoes|the top)|remix|wa7da okhra|why this outfit|pourquoi cette tenue)\b")
_WARDROBE = r"\b((show|list|see|what('s| is) in|open) my (wardrobe|closet|clothes|pieces)|garde-?robe|dressing)\b"
_CHALLENGE = r"\b(challenges?|d[ée]fis?|contest|concours)\b"
_PROFILE = r"\b(my style|what('s| is) my style|style profile|mon style|quel est mon style|chnowa style)\b"
_STYLE = r"\b(i (love|like|hate|don'?t like|prefer)|j'?(aime|adore|d[ée]teste|pr[ée]f[èe]re)|n7eb|nheb|ma n7ebch)\b"
_TRYON = r"\b(try (it )?on|avatar|see it on me|3d)\b"
_GAPS = (r"\b(what (am i|i'?m) missing|what('s| is) missing|what should i buy( next)?|gaps? (in|of) my wardrobe|"
         r"qu'?est-ce qui (me )?manque|ce qui me manque|quoi acheter|chnowa yna9es|chnowa nechri)\b")
_LAUNDRY = r"\b(laundry|lessive|machine|dirty|sale|wash)\b"


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = re.sub(r"(\d)\s*(dt|tnd|dinars?|d)\b", r"\1 tnd", t)  # 320dt / 320 dinars -> 320 tnd
    return re.sub(r"\s+", " ", t).strip()


def _find(words: dict[str, list[str]], low: str) -> str | None:
    best = None
    for key, alts in words.items():
        for w in alts:
            m = re.search(rf"(?<![a-z]){re.escape(w)}s?(?![a-z])", low)
            if m and (best is None or len(w) > best[1]):  # longest match wins ("bleu marine" over "bleu")
                best = (key, len(w))
    return best[0] if best else None


def piece_of(text: str) -> dict:
    """{type, colour, price} found in the text (None when absent)."""
    low = norm(text)
    price = re.search(r"(\d+(?:[.,]\d+)?)\s*tnd", low) or re.search(r"\b(?:at|for|à|a|b|with|pour)\s+(\d{2,4})\b", low)
    return {
        "type": _find(TYPE_WORDS, low),
        "colour": _find(COLOUR_WORDS, low),
        "price": float(price.group(1).replace(",", ".")) if price else None,
    }


def intent_of(text: str) -> str | None:
    """smartbuy | localshop | stylist | wardrobe | challenges | taste | tryon | laundry | None (let the LLM decide)."""
    low = norm(text)
    for name, rx in (("gaps", _GAPS), ("localshop", _SHOP), ("smartbuy", _BUY), ("challenges", _CHALLENGE), ("wardrobe", _WARDROBE),
                     ("tryon", _TRYON), ("laundry", _LAUNDRY), ("stylist", _WEAR), ("profile", _PROFILE), ("taste", _STYLE)):
        if re.search(rx, low):
            return name
    return None


# ---------------------------------------------------------------- follow-ups ("and in black?", "cheaper?")
_FOLLOW = (r"^(and|et|w|wel|what about|how about|and what about|et en|et pour|et si|plut[ôo]t|instead|rather|same|"
           r"the same|la m[êe]me|le m[êe]me|nafs|ok and|then|alors)\b|\b(instead|plut[ôo]t|rather|too|aussi|zeda)\b")
_CHEAPER = r"\b(cheaper|less expensive|moins cher|moins ch[èe]re|arkhes|ar5es|budget)\b"
_WHEN = r"\b(tomorrow|today|tonight|weekend|demain|aujourd'?hui|ce soir|ghodwa|lyoum|lil)\b"
_OCCASION = r"\b(work|office|wedding|party|interview|sport|gym|casual|travail|bureau|mariage|soir[ée]e|entretien|khedma|3ers)\b"


def followup(text: str, intent: str | None, piece: dict, mem: dict):
    """A short message that refines the last request -> (agent, merged piece, message for the agent), else None."""
    low = norm(text)
    agent = mem.get("agent")
    last_piece = mem.get("piece") or {}
    from .replies import city_of

    has_detail = (any(piece.get(k) for k in ("type", "colour", "price")) or re.search(_CHEAPER, low)
                  or (agent == "localshop" and city_of(text)))
    short = len(low.split()) <= 7
    is_follow = re.search(_FOLLOW, low) or (short and not intent and (has_detail or re.search(_WHEN + "|" + _OCCASION, low)))
    if intent and intent != agent:
        return None  # a new kind of request
    if not is_follow and not (intent == agent and not piece.get("type") and last_piece.get("type")):
        return None
    if agent in ("smartbuy", "localshop"):
        merged = {k: piece.get(k) or last_piece.get(k) for k in ("type", "colour", "price")}
        if piece.get("type") and piece.get("type") != last_piece.get("type") and not piece.get("colour"):
            merged["colour"] = None  # another kind of piece: the old colour may not apply
        if re.search(_CHEAPER, low) and not piece.get("price"):
            merged["price"] = round((last_piece.get("price") or 150) * 0.7)
        message = " ".join(x for x in (merged.get("colour"), merged.get("type")) if x) or mem.get("text", "")
        if agent == "localshop":
            from .replies import city_of

            city = city_of(text) or city_of(mem.get("text", ""))
            message = "find " + (message or "clothes") + (f" in {city}" if city else "")
            if merged.get("price"):
                message += f" under {int(merged['price'])} tnd"
        return agent, merged, message
    if agent in ("stylist", "taste", "profile"):
        return "stylist", piece, f"{mem.get('text', '')} — {text}".strip(" —")
    return None
