"""F6.a · demand themes: what users look for, grouped into a few named themes.

Each search is turned into M7's English FashionCLIP prompt ("a photo of women's gold sandals"), from how
M7 understood it (darija already translated). The distinct prompts are embedded with the FashionCLIP text
encoder (same 512-d space as the product photos), clustered with KMeans weighted by their number of
searches, the number of themes chosen by silhouette. A theme is named from its most frequent type, colour
and gender, so names are facts, not LLM text. Searches where nothing was understood are counted apart.
"""

import hashlib
import statistics
from collections import Counter

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from modules.m07_local_catalogue.contract import ParsedQuery
from modules.m07_local_catalogue.pipeline import parse
from modules.m07_local_catalogue.taxonomy import SUBCATEGORIES, SUBCATEGORY_EN

# Theme names are shown in the Espace pro, in English (the catalogue labels are French).
CATEGORY_EN = {
    "top": "Tops",
    "bottom": "Bottoms",
    "dress": "Dresses & sets",
    "outerwear": "Jackets & coats",
    "shoes": "Shoes",
    "accessory": "Accessories",
    "traditional": "Traditional outfits",
}
GENDER_EN = {"women": "women", "men": "men"}


def prompt_of(search: dict) -> str | None:
    parsed = search["data"].get("parsed") or {}
    slots = ParsedQuery(**{k: parsed.get(k) for k in ("category", "subcategory", "color", "gender")})
    return parse.build_prompt(slots, parsed.get("translated") or search.get("value") or "")


def _choose_k(vectors: np.ndarray, weights: np.ndarray, k_min: int, k_max: int) -> tuple[np.ndarray, str]:
    n = len(vectors)
    if n <= k_min:  # few distinct requests: each one is its own theme
        return np.arange(n), f"{n} distinct requests, one theme each"
    best = None
    for k in range(k_min, min(k_max, n - 1) + 1):
        labels = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(vectors, sample_weight=weights)
        if len(set(labels)) < 2:
            continue
        score = silhouette_score(vectors, labels, metric="cosine")
        if best is None or score > best[0]:
            best = (score, k, labels)
    if best is None:
        return np.zeros(n, dtype=int), "one theme"
    return best[2], f"KMeans on FashionCLIP text embeddings, k={best[1]} by silhouette ({best[0]:.2f})"


def _label(members: list[dict]) -> tuple[str, str | None, str | None, str | None, str | None]:
    """Name, subcategory, colour, gender and category of a group, from its most frequent values."""
    parsed = [m["data"].get("parsed") or {} for m in members]
    # ("sub", "shoes") = town shoes; ("cat", "shoes") = "chaussures" in general: same code, not the same thing
    kinds = Counter(
        ("sub", p["subcategory"]) if p.get("subcategory") else ("cat", p.get("category")) for p in parsed
    )
    (level, kind), _ = kinds.most_common(1)[0]
    colours = Counter(p.get("color") for p in parsed if p.get("color"))
    color = (
        colours.most_common(1)[0][0] if colours and colours.most_common(1)[0][1] >= len(parsed) / 2 else None
    )
    genders = Counter(p.get("gender") for p in parsed if p.get("gender"))
    gender = (
        genders.most_common(1)[0][0]
        if genders and genders.most_common(1)[0][1] >= 0.6 * len(parsed)
        else None
    )
    subcategory = kind if level == "sub" else None
    name = SUBCATEGORY_EN.get(kind, kind) if subcategory else CATEGORY_EN.get(kind or "", "Items")
    parts = [name, color.replace("_", " ") if color else None, GENDER_EN.get(gender or "")]
    category = SUBCATEGORIES[kind][0] if subcategory else kind
    return " · ".join(p for p in parts if p), subcategory, color, gender, category


def build(searches: list[dict], encoder, config: dict) -> tuple[list[dict], int, str]:
    """Themes over these searches: [{label, subcategory, color, gender, members, centroid}], number of
    searches not understood, and how the themes were made."""
    prompts = [prompt_of(s) for s in searches]
    understood = [(s, p) for s, p in zip(searches, prompts, strict=True) if p]
    not_understood = len(searches) - len(understood)
    if not understood:
        return [], not_understood, "no search to group"
    counts = Counter(p for _, p in understood)
    distinct = list(counts)
    weights = np.array([counts[p] for p in distinct], dtype=float)
    cfg = config["dashboard"]["themes"]
    if encoder is None:  # no FashionCLIP (fresh clone without the model): one theme per distinct prompt
        vectors, labels, method = None, np.arange(len(distinct)), "no encoder: one theme per distinct request"
    else:
        vectors = np.asarray(encoder.encode_texts(distinct), dtype=np.float32)
        labels, method = _choose_k(vectors, weights, cfg["k_min"], cfg["k_max"])
    of_prompt = dict(zip(distinct, labels, strict=True))

    # Clusters that get the same name ("Sandales · Doré" for weddings and for a budget) are one demand
    # for a shop: they are merged.
    named: dict[str, list[int]] = {}
    for label in sorted(set(labels)):
        members = [s for s, p in understood if of_prompt[p] == label]
        named.setdefault(_label(members)[0], []).append(label)
    themes = []
    for name, cluster_ids in named.items():
        idx = [i for i, p in enumerate(distinct) if of_prompt[p] in cluster_ids]
        members = [s for s, p in understood if of_prompt[p] in cluster_ids]
        _, subcategory, color, gender, category = _label(members)
        centroid = None
        if vectors is not None:
            c = (vectors[idx] * weights[idx, None]).sum(axis=0)
            centroid = c / max(float(np.linalg.norm(c)), 1e-12)
        themes.append(
            {
                "theme_id": "th_" + hashlib.md5(name.encode()).hexdigest()[:6],
                "label": name,
                "subcategory": subcategory,
                "category": category,
                "color": color,
                "gender": gender,
                "members": members,
                "centroid": centroid,
            }
        )
    if len(named) < len(set(labels)):
        method += f", {len(set(labels)) - len(named)} cluster(s) merged with a same-named one"
    return themes, not_understood, method


def exact_answer(data: dict, pieces: dict[str, tuple[str, str]], low_match: float) -> bool:
    """A result of the asked type and colour was shown, with a good match. False when M7 found nothing,
    or relaxed the colour ("no gold sandals: here are other sandals"), or only matched weakly."""
    parsed = data.get("parsed") or {}
    for r in data["results"]:
        sub, color = pieces.get(r["product_id"], (None, None))
        if parsed.get("subcategory") and sub != parsed["subcategory"]:
            continue
        if parsed.get("color") and color != parsed["color"]:
            continue
        if r["match"] >= low_match:
            return True
    return False


def stats(
    theme: dict, members: list[dict], total: int, pieces: dict, low_match: float, n_examples: int
) -> dict:
    """Figures of one theme over a set of its searches (the period).

    `pieces`: product_id -> (type, colour) of the catalogue, to tell exact answers from relaxed ones."""
    data = [m["data"] for m in members]
    budgets = [d["parsed"]["max_price_tnd"] for d in data if (d.get("parsed") or {}).get("max_price_tnd")]
    cities = Counter(
        (d.get("parsed") or {}).get("city") or (d.get("filters") or {}).get("city") for d in data
    )
    cities.pop(None, None)
    weak = [not exact_answer(d, pieces, low_match) for d in data]
    return {
        "theme_id": theme["theme_id"],
        "label": theme["label"],
        "subcategory": theme["subcategory"],
        "color": theme["color"],
        "gender": theme["gender"],
        "n_searches": len(members),
        "share": round(len(members) / max(total, 1), 4),
        "median_budget_tnd": statistics.median(budgets) if budgets else None,
        "top_cities": [c for c, _ in cities.most_common(3)],
        "examples": [
            v for v, _ in Counter((m.get("value") or "").lower() for m in members).most_common(n_examples)
        ],
        "zero_result_rate": round(sum(d["total_matches"] == 0 for d in data) / max(len(data), 1), 3),
        "weak_answer_rate": round(sum(weak) / max(len(weak), 1), 3),
    }
