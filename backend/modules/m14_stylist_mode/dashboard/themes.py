"""F6.a · demand themes: what users look for, grouped into a few named themes.

Each search is turned into M7's English FashionCLIP prompt ("a photo of women's gold sandals"), from how
M7 understood it (darija already translated). The distinct prompts are embedded with the FashionCLIP text
encoder (same 512-d space as the product photos), clustered with KMeans weighted by their number of
searches, the number of themes chosen by silhouette. A theme is named from its most frequent type, colour
and gender, so names are facts, not LLM text. Searches where nothing was understood are counted apart.
"""

import hashlib
import statistics
import threading
import time
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


# The clustering is the slow part (~10 s for 300 distinct requests on a CPU). It is kept `cache_minutes`
# (config.yaml) per log set: a request first seen since then joins the theme of its nearest centroid.
# Older themes are still used while a new clustering runs in the background, so only the very first
# dashboard of the server waits. The FashionCLIP vector of a request is computed once.
_vectors: dict[tuple[int, str], np.ndarray] = {}
_clusters: dict[tuple, dict] = {}
_refreshing: set[tuple] = set()
_lock = threading.Lock()


def reset_cache() -> None:
    _vectors.clear()
    _clusters.clear()


def _embed(encoder, prompts: list[str]) -> np.ndarray:
    missing = [p for p in prompts if (id(encoder), p) not in _vectors]
    if missing:
        for p, v in zip(missing, encoder.encode_texts(missing), strict=True):
            _vectors[(id(encoder), p)] = np.asarray(v, dtype=np.float32)
    return np.stack([_vectors[(id(encoder), p)] for p in prompts])


def _remember(key: tuple, distinct: list[str], vectors: np.ndarray, weights: np.ndarray, cfg: dict) -> dict:
    labels, method = _choose_k(vectors, weights, cfg["k_min"], cfg["k_max"])
    centroids = np.zeros((int(labels.max()) + 1, vectors.shape[1]), dtype=np.float32)
    for label in set(labels.tolist()):
        c = (vectors[labels == label] * weights[labels == label, None]).sum(axis=0)
        centroids[label] = c / max(float(np.linalg.norm(c)), 1e-12)
    entry = {
        "at": time.monotonic(),
        "label_of": dict(zip(distinct, labels.tolist(), strict=True)),
        "centroids": centroids,
        "method": method,
    }
    _clusters[key] = entry
    return entry


def _refresh(key: tuple, distinct: list[str], vectors: np.ndarray, weights: np.ndarray, cfg: dict) -> None:
    with _lock:
        if key in _refreshing:
            return
        _refreshing.add(key)

    def run():
        try:
            _remember(key, distinct, vectors, weights, cfg)
        finally:
            _refreshing.discard(key)

    threading.Thread(target=run, daemon=True).start()


def _cluster(
    distinct: list[str], vectors: np.ndarray, weights: np.ndarray, cfg: dict, key: tuple | None
) -> tuple[np.ndarray, str]:
    minutes = cfg.get("cache_minutes", 0)
    if not minutes or key is None:
        return _choose_k(vectors, weights, cfg["k_min"], cfg["k_max"])
    entry = _clusters.get(key)
    if entry is None:
        entry = _remember(key, distinct, vectors, weights, cfg)
    elif time.monotonic() - entry["at"] > minutes * 60:
        _refresh(key, distinct, vectors, weights, cfg)
    labels = np.array([entry["label_of"].get(p, -1) for p in distinct])
    new = labels < 0
    if new.any():
        labels[new] = np.argmax(vectors[new] @ entry["centroids"].T, axis=1)
    age = int((time.monotonic() - entry["at"]) // 60)
    method = entry["method"] + f"; themes of {age} min ago (cache {minutes} min)"
    if new.any():
        method += f", {int(new.sum())} new request(s) joined the nearest theme"
    return labels, method


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


def build(
    searches: list[dict], encoder, config: dict, cache_key: tuple | None = None
) -> tuple[list[dict], int, str]:
    """Themes over these searches: [{label, subcategory, color, gender, members, centroid}], number of
    searches not understood, and how the themes were made. `cache_key` names the logs read (see _cluster)."""
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
        vectors = _embed(encoder, distinct)
        labels, method = _cluster(distinct, vectors, weights, cfg, cache_key)
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
