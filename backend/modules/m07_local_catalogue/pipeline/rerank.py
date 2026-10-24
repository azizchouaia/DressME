"""Re-rank with the user's style vector, then diversify (MMR) and explain each result.

match = weighted mean of the parts that apply to the request, each in 0..1:
  visual      FashionCLIP query (text or photo) vs product photo, cosine mapped to 0..1
  text        BM25 relative to the best candidate
  attributes  requested subcategory / colour / gender present on the product (unknown = 0.5)
  style       user's style vector vs product photo
  season      summer / winter asked: the piece's name and type say that season (1), the other one (0)
  budget      no budget asked but a usual one learned from memory: price within it (1), far above (0)
Weights come from config.yaml and are renormalised over the parts available for each product.
"""

import numpy as np

from ..contract import ParsedQuery
from ..taxonomy import COLOR_CODES, GENDERS, GENDERS_AR, GENDERS_EN, colour_name, governorate, label
from .context import phrase


def _scale(x: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def score(
    catalogue,
    candidates: np.ndarray,
    parsed: ParsedQuery,
    visual: np.ndarray | None,
    visual_kind: str | None,
    bm25: np.ndarray,
    style_vector: np.ndarray | None,
    config: dict,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Match score (0..1) of each candidate index, plus every part (NaN where it does not apply)."""
    n = len(candidates)
    has_emb = catalogue.has_embedding[candidates]
    parts: dict[str, np.ndarray] = {}

    if visual is not None:
        lo, hi = config["visual_image_range"] if visual_kind == "image" else config["visual_text_range"]
        parts["visual"] = np.where(has_emb, _scale(visual[candidates], lo, hi), np.nan)
    best = float(bm25[candidates].max()) if n else 0.0
    if parsed.terms and best > 0:
        parts["text"] = bm25[candidates] / best

    checks = []
    if parsed.subcategory or parsed.category:
        checks.append(np.ones(n))  # guaranteed by the filters, keeps 'match' comparable across queries
    if parsed.color:
        colors = catalogue.color[candidates]
        checks.append(np.where(colors == parsed.color, 1.0, np.where(colors == "", 0.5, 0.0)))
    if parsed.gender in ("women", "men"):
        genders = catalogue.gender[candidates]  # the other gender is already filtered out
        checks.append(np.where((genders == parsed.gender) | (genders == "unisex"), 1.0, 0.5))
    if checks:
        parts["attributes"] = np.mean(checks, axis=0)

    if style_vector is not None:
        style = catalogue.embeddings[candidates] @ style_vector
        parts["style"] = np.where(has_emb, _scale(style, *config["style_range"]), np.nan)

    if parsed.season:
        sign = 1 if parsed.season == "summer" else -1
        parts["season"] = (catalogue.season[candidates] * sign + 1) / 2  # 1 its season, 0.5 neutral, 0 other

    if parsed.usual_budget_tnd and parsed.max_price_tnd is None:
        price = catalogue.price[candidates]
        margin = parsed.usual_budget_tnd * config["budget_memory"]["tolerance"]
        over = (price - parsed.usual_budget_tnd) / margin
        parts["budget"] = np.where(np.isnan(price), 0.5, np.clip(1 - over, 0.0, 1.0))

    weights = config["weights"]
    total = np.zeros(n)
    weight_sum = np.zeros(n)
    for name, values in parts.items():
        present = ~np.isnan(values)
        total += np.where(present, values * weights[name], 0.0)
        weight_sum += np.where(present, weights[name], 0.0)
    match = np.divide(total, weight_sum, out=np.zeros(n), where=weight_sum > 0)
    return match, parts


MMR_POOL = 2000  # fixed (not tied to k), so the first n picks are the same whatever the page size


def mmr(catalogue, candidates: np.ndarray, match: np.ndarray, k: int, lam: float) -> list[int]:
    """Maximal marginal relevance: avoid returning k near-identical photos (same model in 5 colours)."""
    order = np.argsort(-match, kind="stable")[:MMR_POOL]
    emb = catalogue.embeddings[candidates[order]]
    chosen: list[int] = []
    max_sim = np.zeros(len(order))
    while len(chosen) < min(k, len(order)):
        gain = lam * match[order] - (1 - lam) * max_sim
        gain[chosen] = -np.inf
        best = int(np.argmax(gain))
        chosen.append(best)
        max_sim = np.maximum(max_sim, emb @ emb[best])
    return [int(order[i]) for i in chosen]


# Reasons in the request's language (Arabic answers keep the French reasons for now).
REASONS = {
    "fr": {
        "colour": "Couleur : {c}",
        "colour_unknown": "Couleur non précisée par la boutique : vérifier sur la photo",
        "other_colour": "Autre couleur : {c}",
        "model": "Modèle {g}",
        "from_photo": "{label} (estimé d'après la photo)",
        "gender_unknown": "Genre non précisé par la boutique",
        "budget": "{price} (budget {max:g} TND)",
        "shop_in": "Boutique à {city}",
        "shop_near": "Boutique à {city} (près de {asked})",
        "chain": "Chaîne présente dans {n} villes ({cities}…)",
        "like_photo": "Très proche de la photo",
        "looks_like": "Ressemble visuellement à la demande",
        "style": "Proche de ton style",
        "local_brand": "Marque tunisienne",
        "occasion": "Pour {o}",
        "season": "Pièce pour {s}",
        "usual_budget": "Dans ton budget habituel (≤ {max:g} TND)",
        "loyalty": "Code fidélité {code} : −{pct} %",
    },
    "en": {
        "colour": "Colour: {c}",
        "colour_unknown": "Colour not given by the shop: check the photo",
        "other_colour": "Other colour: {c}",
        "model": "{g} piece",
        "from_photo": "{label} (estimated from the photo)",
        "gender_unknown": "Gender not given by the shop",
        "budget": "{price} (budget {max:g} TND)",
        "shop_in": "Shop in {city}",
        "shop_near": "Shop in {city} (near {asked})",
        "chain": "Chain in {n} cities ({cities}…)",
        "like_photo": "Very close to the photo",
        "looks_like": "Looks like the request",
        "style": "Close to your style",
        "local_brand": "Tunisian brand",
        "occasion": "For {o}",
        "season": "A piece for {s}",
        "usual_budget": "Within your usual budget (≤ {max:g} TND)",
        "loyalty": "Loyalty code {code}: −{pct}%",
    },
    "ar": {
        "colour": "اللون: {c}",
        "colour_unknown": "اللون غير محدد من المتجر: تحقق من الصورة",
        "other_colour": "لون آخر: {c}",
        "model": "موديل {g}",
        "from_photo": "{label} (مقدّر من الصورة)",
        "gender_unknown": "الجنس غير محدد من المتجر",
        "budget": "{price} (الميزانية {max:g} دينار)",
        "shop_in": "متجر في {city}",
        "shop_near": "متجر في {city} (قرب {asked})",
        "chain": "سلسلة موجودة في {n} مدن ({cities}…)",
        "like_photo": "قريبة جدًا من الصورة",
        "looks_like": "تشبه الطلب بصريًا",
        "style": "قريبة من أسلوبك",
        "local_brand": "علامة تونسية",
        "occasion": "لـ{o}",
        "season": "قطعة لـ{s}",
        "usual_budget": "ضمن ميزانيتك المعتادة (≤ {max:g} دينار)",
        "loyalty": "رمز الوفاء {code}: −{pct}٪",
    },
}


def reasons(
    product: dict,
    parsed: ParsedQuery,
    parts: dict[str, np.ndarray],
    j: int,
    visual_kind: str | None,
    language: str = "fr",
) -> list[str]:
    """Short reasons built only from the product data and the computed scores."""
    t = REASONS.get(language, REASONS["fr"])
    out = []
    if parsed.subcategory:
        out.append(label(parsed.subcategory, language))
    if parsed.occasion:
        out.append(t["occasion"].format(o=phrase(parsed.occasion, language)))
    season = parts.get("season")
    if season is not None and season[j] == 1:
        out.append(t["season"].format(s=phrase(parsed.season, language)))
    if parsed.color:
        if product.get("color") == parsed.color:
            out.append(t["colour"].format(c=colour_name(parsed.color, language)))
        elif not product.get("color"):
            out.append(t["colour_unknown"])
        else:
            other = (
                colour_name(product["color"], language)
                if language != "fr" and product["color"] in COLOR_CODES
                else product.get("color_fr", "").lower()
            )
            out.append(t["other_colour"].format(c=other))
    if parsed.gender in ("women", "men"):
        gender = product.get("gender") or ""
        if gender in GENDERS:
            name = {"en": GENDERS_EN, "ar": GENDERS_AR}.get(language, {}).get(gender) or GENDERS[
                gender
            ].lower()
            model = t["model"].format(g=name)
            out.append(
                t["from_photo"].format(label=model) if product.get("gender_source") == "photo" else model
            )
        else:
            out.append(t["gender_unknown"])
    if product.get("price_tnd") is not None:
        price = f"{product['price_tnd']:g} TND"
        out.append(
            t["budget"].format(price=price, max=parsed.max_price_tnd) if parsed.max_price_tnd else price
        )
        budget = parts.get("budget")
        if budget is not None and budget[j] == 1:
            out.append(t["usual_budget"].format(max=parsed.usual_budget_tnd))
    cities = [c for c in (product.get("city") or "").split("; ") if c]
    if parsed.city and parsed.city in cities:
        out.append(t["shop_in"].format(city=parsed.city))
    elif parsed.city and cities:
        local = [c for c in cities if governorate(c) == parsed.governorate]
        out.append(
            t["shop_near"].format(city=local[0], asked=parsed.city)
            if local
            else t["shop_in"].format(city=cities[0])
        )
    elif len(cities) > 3:
        out.append(t["chain"].format(n=len(cities), cities=", ".join(cities[:3])))
    elif cities:
        out.append(t["shop_in"].format(city=", ".join(cities)))
    visual = parts.get("visual")
    if visual is not None and not np.isnan(visual[j]) and visual[j] >= 0.6:
        out.append(t["like_photo"] if visual_kind == "image" else t["looks_like"])
    style = parts.get("style")
    if style is not None and not np.isnan(style[j]) and style[j] >= 0.6:
        out.append(t["style"])
    if product.get("origin_type") == "local_brand":
        out.append(t["local_brand"])
    return out
