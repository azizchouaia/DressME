"""F7.b · which stylist? Weighted score, renormalised over the parts that apply (weights in config.yaml):

    speciality  stylist's specialities vs the occasion / pieces of the chat (1 - speciality_decay^matches)
    style       cosine(client style vector from M5, stylist portfolio vector), when both exist
    city        same city (1) or same governorate (config same_governorate)
    language    speaks the client's language
    load        1 - open hand-offs / max_load (a full stylist is not proposed)

Later: learning-to-rank from accepted / declined hand-offs, same output.
"""

import numpy as np

from modules.m07_local_catalogue.scraper.normalize import fold
from modules.m07_local_catalogue.taxonomy import canonical_city, governorate

LANGUAGE_WORDS = {
    "fr": {"fr", "francais"},
    "en": {"en", "english", "anglais"},
    "ar": {"ar", "arabe", "arabic", "darija", "tn"},
}


def _speciality(pro: dict, wanted: set[str], decay: float) -> tuple[float, str | None]:
    """1 - decay^n for n specialities said in the chat (decay 0.5): "costume homme mariage" ranks a suit +
    men + wedding stylist (0.875) above a wedding-only one (0.5)."""
    common = [s for s in pro.get("specialities") or [] if fold(s) in wanted]  # as the stylist wrote them
    return (1 - decay ** len(common), f"Spécialité : {', '.join(common)}") if common else (0.0, None)


def _city(pro: dict, city: str | None, same_governorate: float) -> tuple[float, str | None]:
    a, b = canonical_city(pro.get("city") or ""), canonical_city(city or "")
    if not (a and b):
        return 0.0, None
    if a == b:
        return 1.0, f"Même ville : {a}"
    if governorate(a) and governorate(a) == governorate(b):
        return same_governorate, f"Près de chez vous : {a}"
    return 0.0, None


def _style(pro: dict, client_vector: list[float] | None) -> float | None:
    if not (client_vector and pro.get("style_vector")):
        return None
    a, b = np.asarray(client_vector, dtype=float), np.asarray(pro["style_vector"], dtype=float)
    return float(np.clip((a @ b) / max(np.linalg.norm(a) * np.linalg.norm(b), 1e-12), 0, 1))


def rank(
    pros: list[dict],
    open_load: dict[str, int],
    wanted: set[str],
    city: str | None,
    language: str,
    client_vector: list[float] | None,
    config: dict,
) -> list[dict]:
    cfg = config["handoff"]
    weights = cfg["weights"]
    out = []
    for pro in pros:
        if pro["type"] != "stylist" or not pro.get("available", True):
            continue
        load = open_load.get(pro["pro_id"], 0)
        if load >= cfg["max_load"]:
            continue
        parts, reasons = {}, []
        parts["speciality"], why = _speciality(pro, wanted, cfg["speciality_decay"])
        reasons += [why] if why else []
        parts["city"], why = _city(pro, city, cfg["same_governorate"])
        reasons += [why] if why else []
        speaks = {fold(x) for x in pro.get("languages") or []}
        parts["language"] = 1.0 if speaks & LANGUAGE_WORDS[language] else 0.0
        if parts["language"]:
            reasons.append(f"Parle {language}")
        parts["load"] = 1 - load / cfg["max_load"]
        style = _style(pro, client_vector)
        if style is not None:
            parts["style"] = style
            reasons.append(f"Style proche ({style:.0%})")
        total = sum(weights[k] for k in parts)
        score = sum(weights[k] * v for k, v in parts.items()) / total
        out.append(
            {
                "pro_id": pro["pro_id"],
                "name": pro["name"],
                "city": pro.get("city"),
                "score": round(score, 3),
                "reasons": reasons,
            }
        )
    return sorted(out, key=lambda c: -c["score"])[: cfg["candidates"]]
