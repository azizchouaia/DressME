"""Rule engine: each rule returns the list of violations for today's outfit (empty list = valid).

A rule sees today's garments and the garments of the previous entries of the same user in the same challenge.
Adding a new challenge type = adding one function to RULES.
"""

from collections.abc import Callable

from shared.schemas import Garment

RuleFn = Callable[[dict, list[Garment], list[tuple[int, list[Garment]]]], list[str]]


def _name(g: Garment) -> str:
    return g.subcategory or g.category.value


def dominant_color(g: Garment) -> str | None:
    if not g.colors:
        return None
    return max(g.colors, key=lambda c: c.share).name.lower()


def no_repeat(params: dict, today: list[Garment], previous: list[tuple[int, list[Garment]]]) -> list[str]:
    seen: dict[str, int] = {}
    for day, items in previous:
        for g in items:
            seen.setdefault(g.item_id, day)
    return [f"{_name(g)} already worn on day {seen[g.item_id]}" for g in today if g.item_id in seen]


def color_theme(params: dict, today: list[Garment], previous: list[tuple[int, list[Garment]]]) -> list[str]:
    colors = {c.lower() for c in params.get("colors", [])}
    mode = params.get("mode", "all")
    matching = [g for g in today if dominant_color(g) in colors]
    if mode == "any":
        return [] if matching else [f"wear at least one piece in {', '.join(sorted(colors))}"]
    return [
        f"{_name(g)} is {dominant_color(g) or 'unknown colour'}, not in the theme"
        for g in today
        if g not in matching
    ]


def category_required(
    params: dict, today: list[Garment], previous: list[tuple[int, list[Garment]]]
) -> list[str]:
    cats = set(params.get("categories", []))
    need = int(params.get("min", 1))
    have = sum(1 for g in today if g.category.value in cats or (g.subcategory or "") in cats)
    return [] if have >= need else [f"include at least {need} piece(s) from: {', '.join(sorted(cats))}"]


def capsule_limit(params: dict, today: list[Garment], previous: list[tuple[int, list[Garment]]]) -> list[str]:
    limit = int(params.get("max_distinct", 10))
    used = {g.item_id for _, items in previous for g in items}
    new = [g for g in today if g.item_id not in used]
    if len(used) + len(new) <= limit:
        return []
    return [
        f"capsule limit is {limit} pieces: you already used {len(used)}, "
        f"{_name(new[0])} would be piece {len(used) + 1}"
    ]


def local_brand(params: dict, today: list[Garment], previous: list[tuple[int, list[Garment]]]) -> list[str]:
    need = int(params.get("min", 1))
    have = sum(1 for g in today if g.local_tag)
    return [] if have >= need else [f"wear at least {need} piece(s) from a Tunisian brand"]


def min_items(params: dict, today: list[Garment], previous: list[tuple[int, list[Garment]]]) -> list[str]:
    need = int(params.get("min", 3))
    return [] if len(today) >= need else [f"an outfit needs at least {need} pieces (you logged {len(today)})"]


RULES: dict[str, RuleFn] = {
    "no_repeat": no_repeat,
    "color_theme": color_theme,
    "category_required": category_required,
    "capsule_limit": capsule_limit,
    "local_brand": local_brand,
    "min_items": min_items,
}


KNOWN_COLORS = {
    "black",
    "white",
    "grey",
    "beige",
    "brown",
    "red",
    "pink",
    "orange",
    "yellow",
    "green",
    "blue",
    "navy",
    "purple",
}
CATEGORIES = {"top", "bottom", "dress", "outerwear", "shoes", "accessory", "traditional"}


def validate(rules: list[dict], duration: int) -> list[str]:
    """Checks a new challenge before it is published. Returns the problems (empty list = OK)."""
    errors: list[str] = []
    types = [r["type"] for r in rules]
    if len(types) != len(set(types)):
        errors.append("each rule type can be used once")
    for r in rules:
        t, p = r["type"], r.get("params", {})
        if t == "color_theme":
            cols = {c.lower() for c in p.get("colors", [])}
            if not cols:
                errors.append("color_theme needs at least one colour")
            elif cols - KNOWN_COLORS:
                errors.append(f"unknown colour(s): {', '.join(sorted(cols - KNOWN_COLORS))}")
            if p.get("mode", "all") not in ("all", "any"):
                errors.append("color_theme mode is 'all' or 'any'")
        elif t == "category_required":
            cats = set(p.get("categories", []))
            if not cats:
                errors.append("category_required needs at least one category")
        elif t == "capsule_limit":
            n = int(p.get("max_distinct", 10))
            if n < 3:
                errors.append("capsule_limit needs at least 3 pieces")
        elif t in ("min_items", "local_brand"):
            n = int(p.get("min", 1))
            if not 1 <= n <= 6:
                errors.append(f"{t} min must be between 1 and 6")
    if "no_repeat" in types and "capsule_limit" in types:
        errors.append("no_repeat and capsule_limit contradict each other (a capsule re-uses pieces)")
    return errors


def run_by_rule(
    rules: list[dict], today: list[Garment], previous: list[tuple[int, list[Garment]]]
) -> list[tuple[str, str]]:
    """Same as run(), each violation with the type of the rule it breaks (for the coach's memory)."""
    return [(r["type"], v) for r in rules for v in RULES[r["type"]](r.get("params", {}), today, previous)]


def run(rules: list[dict], today: list[Garment], previous: list[tuple[int, list[Garment]]]) -> list[str]:
    """rules: [{"type", "params"}] → all violations, in rule order."""
    return [v for _, v in run_by_rule(rules, today, previous)]
