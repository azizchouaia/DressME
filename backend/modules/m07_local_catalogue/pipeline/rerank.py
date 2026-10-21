"""Re-rank with the user's style vector, then diversify (MMR) and explain each result.

match = weighted mean of the parts that apply to the request, each in 0..1:
  visual      FashionCLIP query (text or photo) vs product photo, cosine mapped to 0..1
  text        BM25 relative to the best candidate
  attributes  requested subcategory / colour / gender present on the product (unknown = 0.5)
  style       user's style vector vs product photo
Weights come from config.yaml and are renormalised over the parts available for each product.
"""

import numpy as np

from ..contract import ParsedQuery
from ..taxonomy import COLOR_CODES, GENDERS, SUBCATEGORIES, governorate


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


def reasons(
    product: dict,
    parsed: ParsedQuery,
    parts: dict[str, np.ndarray],
    j: int,
    visual_kind: str | None,
) -> list[str]:
    """Short French reasons built only from the product data and the computed scores."""
    out = []
    if parsed.subcategory:
        out.append(SUBCATEGORIES[parsed.subcategory][1])
    if parsed.color:
        wanted = COLOR_CODES[parsed.color][0].lower()
        if product.get("color") == parsed.color:
            out.append(f"Couleur : {wanted}")
        elif not product.get("color"):
            out.append("Couleur non précisée par la boutique : vérifier sur la photo")
        else:
            out.append(f"Autre couleur : {product.get('color_fr', '').lower()}")
    if parsed.gender in ("women", "men"):
        gender = product.get("gender") or ""
        if gender in GENDERS:
            label = f"Modèle {GENDERS[gender].lower()}"
            out.append(
                f"{label} (estimé d'après la photo)" if product.get("gender_source") == "photo" else label
            )
        else:
            out.append("Genre non précisé par la boutique")
    if product.get("price_tnd") is not None:
        price = f"{product['price_tnd']:g} TND"
        out.append(f"{price} (budget {parsed.max_price_tnd:g} TND)" if parsed.max_price_tnd else price)
    cities = [c for c in (product.get("city") or "").split("; ") if c]
    if parsed.city and parsed.city in cities:
        out.append(f"Boutique à {parsed.city}")
    elif parsed.city and cities:
        local = [c for c in cities if governorate(c) == parsed.governorate]
        out.append(f"Boutique à {local[0]} (près de {parsed.city})" if local else f"Boutique à {cities[0]}")
    elif len(cities) > 3:
        out.append(f"Chaîne présente dans {len(cities)} villes ({', '.join(cities[:3])}…)")
    elif cities:
        out.append(f"Boutique à {', '.join(cities)}")
    visual = parts.get("visual")
    if visual is not None and not np.isnan(visual[j]) and visual[j] >= 0.6:
        out.append(
            "Très proche de la photo" if visual_kind == "image" else "Ressemble visuellement à la demande"
        )
    style = parts.get("style")
    if style is not None and not np.isnan(style[j]) and style[j] >= 0.6:
        out.append("Proche de ton style")
    if product.get("origin_type") == "local_brand":
        out.append("Marque tunisienne")
    return out
