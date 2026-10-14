"""Hard filters: price (TND), city, category / subcategory, stock. Colour stays a soft score (rerank)."""

import numpy as np

from ..contract import ParsedQuery
from ..taxonomy import canonical_city, governorate


def city_mask(catalogue, city: str | None) -> np.ndarray:
    """Shops in the requested city or anywhere in its governorate (La Marsa matches 'Tunis').

    Shops with no published address never match a city filter: we do not know where they are.
    """
    if not city:
        return np.ones(len(catalogue), dtype=bool)
    name = canonical_city(city) or city.strip()
    gov = governorate(name)
    return np.array(
        [
            name in cities or (gov is not None and gov in govs)
            for cities, govs in zip(catalogue.cities, catalogue.governorates, strict=True)
        ],
        dtype=bool,
    )


def run(
    catalogue, parsed: ParsedQuery, include_unavailable: bool = False, use_city: bool = True
) -> np.ndarray:
    mask = np.ones(len(catalogue), dtype=bool)
    if not include_unavailable:
        mask &= catalogue.available
    if parsed.max_price_tnd is not None:
        mask &= catalogue.price <= parsed.max_price_tnd  # NaN prices fail both comparisons
    if parsed.min_price_tnd is not None:
        mask &= catalogue.price >= parsed.min_price_tnd
    if parsed.subcategory:
        mask &= catalogue.subcategory == parsed.subcategory
    elif parsed.category:
        mask &= catalogue.category == parsed.category
    if use_city and parsed.city:
        mask &= city_mask(catalogue, parsed.city)
    return mask
