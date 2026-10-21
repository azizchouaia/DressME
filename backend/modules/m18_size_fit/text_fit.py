"""M18 — read fit from free text: "I wear M at Zara but it's tight on the shoulders".

Text -> [{brand, size, category, fit, part}] + like_fit, then service.advise() does the rest.
Two levels:
1. rules (always): keywords FR / EN / Tunisian, sizes, brands, strength words ("a bit", "very", "barcha")
2. LLM (optional, Ollama llama3.1): for long / messy text; strict JSON, checked; falls back to the rules
"""

import json
import os
import re

FITS = ("extremely_tight", "tight", "normal", "loose", "oversized")
LIKES = ("tight", "normal", "loose", "oversized")

TIGHT = ["tight", "small", "narrow", "serré", "serre", "petit", "étroit", "etroit", "moulant", "dayyeq", "dayek",
         "dhayek", "sghir"]
LOOSE = ["loose", "big", "wide", "baggy", "large", "grand", "ample", "wase3", "wesa3", "wasa3", "kbir"]
OVERSIZED = ["oversize", "oversized"]
NORMAL = ["perfect", "fine", "fits well", "good fit", "true to size", "normal", "nickel", "parfait", "bien",
          "mezyen", "behi", "mrigel"]
STRONG = ["very", "too", "really", "extremely", "super", "trop", "très", "tres", "vraiment", "barcha", "barsha", "yesser"]
WEAK = ["a bit", "a little", "slightly", "un peu", "légèrement", "legerement", "chwaya", "shwaya"]
PARTS = {"shoulders": ["shoulder", "épaule", "epaule", "ktef"], "chest": ["chest", "poitrine", "sder"],
         "waist": ["waist", "taille", "belly", "ventre", "kerch"], "hips": ["hip", "hanche"],
         "sleeves": ["sleeve", "manche", "kmem"], "length": ["length", "long", "short", "court", "longueur", "twil", "9sir"],
         "thighs": ["thigh", "cuisse"]}
CATEGORY = {"top": ["shirt", "t-shirt", "tshirt", "top", "sweater", "pull", "hoodie", "chemise", "blouse", "polo",
                    "tricot", "sweat", "maryoul", "souriya", "jacket", "veste", "blazer", "coat", "manteau"],
            "bottom": ["jean", "jeans", "pant", "pants", "trouser", "pantalon", "skirt", "jupe", "shorts", "chino",
                       "serwel", "sarwel"],
            "dress": ["dress", "robe", "jebba"]}
LIKE_WORDS = ["i like", "i prefer", "i love", "j'aime", "je préfère", "je prefere", "n7eb", "nheb", "nhebb", "n7ebb"]
SIZE_RE = re.compile(r"(?<![A-Za-z0-9])(XXXL|3XL|XXL|2XL|XL|XS|XXS|S|M|L|3[4-9]|4[0-9]|5[0-6])(?![A-Za-z0-9])")
SPLIT_RE = re.compile(r"[.;!\n]|,| but | and | mais | et | w | ama | however ", re.I)


def _has(text: str, words: list[str]) -> bool:
    return any(re.search(r"(?<![a-z])" + re.escape(w), text) for w in words)


def _fit(clause: str) -> str | None:
    low = clause.lower()
    if _has(low, OVERSIZED):
        return "oversized"
    strong, weak = _has(low, STRONG), _has(low, WEAK)
    if _has(low, TIGHT):
        return "extremely_tight" if strong and not weak else "tight"
    if _has(low, LOOSE):
        return "oversized" if strong and not weak else "loose"
    if _has(low, NORMAL):
        return "normal"
    return None


def _category(low: str) -> str | None:
    for cat, words in CATEGORY.items():
        if _has(low, words):
            return cat
    return None


def _part(low: str) -> str | None:
    return next((p for p, words in PARTS.items() if _has(low, words)), None)


def _brand_in(brand: str, low: str) -> bool:
    """'Carthage Denim Co.' matches 'carthage denim' and 'carthage'."""
    words = [w for w in re.findall(r"[a-z0-9&']+", brand.lower()) if w not in ("co", "the", "inc")]
    return bool(words) and (" ".join(words) in low or re.search(r"(?<![a-z])" + re.escape(words[0]), low) is not None)


def parse_rules(text: str, brands: list[str]) -> dict:
    """-> {refs: [...], like_fit, unclear: [clauses we could not read]}"""
    refs, like, unclear = [], None, []
    last_brand = last_size = last_cat = None
    for clause in (c.strip() for c in SPLIT_RE.split(text or "")):
        if not clause:
            continue
        low = clause.lower()
        fit = _fit(clause)
        if _has(low, LIKE_WORDS) and fit in ("tight", "loose", "oversized", "normal"):
            like = fit
            continue
        brand = next((b for b in brands if _brand_in(b, low)), None) or last_brand
        sizes = SIZE_RE.findall(clause)
        size = sizes[0] if sizes else last_size
        cat = _category(low) or last_cat or "top"
        if fit and brand and size:
            refs.append({"brand": brand, "size": size, "category": cat, "fit": fit, "part": _part(low)})
        elif fit:
            unclear.append(clause)  # how it fits, but which brand / size? -> LLM or a question
        last_brand, last_size, last_cat = brand, size, cat
    return {"refs": refs, "like_fit": like, "unclear": unclear, "method": "rules"}


PROMPT = """Extract clothing fit facts from the user's text. Answer ONLY with JSON:
{{"refs":[{{"brand":"...","size":"...","category":"top|bottom|dress","fit":"extremely_tight|tight|normal|loose|oversized","part":"shoulders|chest|waist|hips|sleeves|length|thighs|null"}}],"like_fit":"tight|normal|loose|oversized|null"}}
Rules: only facts written in the text, no guesses. Brand must be one of: {brands}. Size as written (S, M, L, 40...).
like_fit only if the user says how they LIKE to wear clothes.
Text: \"\"\"{text}\"\"\""""


def _clean(data: dict, brands: list[str]) -> dict:
    """Keep only valid facts from the LLM: known brand, a size, known fit words."""
    by_low = {b.lower(): b for b in brands}
    refs = []
    for r in data.get("refs") or []:
        b = by_low.get(str(r.get("brand", "")).lower())
        size = str(r.get("size") or "").upper().strip()
        if b and SIZE_RE.fullmatch(size) and r.get("fit") in FITS:
            refs.append({"brand": b, "size": size, "fit": r["fit"],
                         "category": r.get("category") if r.get("category") in CATEGORY else "top",
                         "part": r.get("part") if r.get("part") in PARTS else None})
    like = data.get("like_fit") if data.get("like_fit") in LIKES else None
    return {"refs": refs, "like_fit": like, "unclear": [], "method": "llm"}


def parse_llm(text: str, brands: list[str], timeout: float = 25.0) -> dict | None:
    """Ollama (local, free). None if it is not running, too slow or answers nonsense."""
    try:
        import httpx
        r = httpx.post(os.environ.get("OLLAMA_URL", "http://localhost:11434") + "/api/chat", timeout=timeout, json={
            "model": os.environ.get("OLLAMA_MODEL", "llama3.1:8b"), "stream": False, "format": "json",
            "options": {"temperature": 0},
            "messages": [{"role": "user", "content": PROMPT.format(brands=", ".join(brands), text=text)}]})
        r.raise_for_status()
        out = _clean(json.loads(r.json()["message"]["content"]), brands)
        return out if out["refs"] or out["like_fit"] else None
    except Exception:  # noqa: BLE001 - LLM is optional
        return None


def parse(text: str, brands: list[str], use_llm: bool = True) -> dict:
    """Rules first; the LLM only when the rules miss something (unclear parts or nothing found)."""
    rules = parse_rules(text, brands)
    if use_llm and (rules["unclear"] or not rules["refs"]):
        llm = parse_llm(text, brands)
        if llm and len(llm["refs"]) >= len(rules["refs"]):
            llm["like_fit"] = llm["like_fit"] or rules["like_fit"]
            return llm
    return rules


PART_TIP = {"shoulders": "check the shoulder seam", "sleeves": "check the sleeve length",
            "length": "check the length", "waist": "check the waist", "chest": "check the chest",
            "hips": "check the hips", "thighs": "check the thighs"}


def part_tips(refs: list[dict]) -> list[str]:
    return [f"{r['brand']} {r['size']} felt {r['fit'].replace('_', ' ')} at the {r['part']}: {PART_TIP[r['part']]}"
            for r in refs if r.get("part") in PART_TIP and r["fit"] != "normal"]
