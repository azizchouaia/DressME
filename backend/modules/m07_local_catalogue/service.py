"""Real implementation of M7: one shared LocalShopAgent (catalogue + FashionCLIP loaded once).

The knowledge base lives in ml/data/shops/ (DVC, not git). On a clone without it, every function
answers with mock.py's fixed data instead of failing, so the modules that call M7 are never blocked.
"""

import logging
from collections import Counter

from . import mock
from .agent import LocalShopAgent
from .paths import CATALOGUE_CSV

log = logging.getLogger("m07.service")
_agent: LocalShopAgent | None = None


def knowledge_base_ready() -> bool:
    return CATALOGUE_CSV.is_file()


async def get_agent() -> LocalShopAgent:
    """The agent used by the API and the orchestrator tool; loads the knowledge base on first use."""
    global _agent
    if _agent is None:
        _agent = LocalShopAgent()
    if _agent.catalogue is None:
        await _agent.setup()
    return _agent


async def search(req: dict) -> dict:
    """LocalShopInput (dict) -> LocalShopOutput (dict). Raises AgentError / ValidationError on bad input."""
    if not knowledge_base_ready():
        log.warning("M7 knowledge base %s missing: serving mock.py (dvc pull or rebuild it)", CATALOGUE_CSV)
        return mock.search(req)
    return await (await get_agent())(req)


async def shops() -> list[dict]:
    if not knowledge_base_ready():
        return mock.shops()
    products = (await get_agent()).catalogue.products
    counts = Counter(p["shop_name"] for p in products)
    first: dict[str, dict] = {}
    for p in products:
        first.setdefault(p["shop_name"], p)
    return [
        {
            "shop": name,
            "city": first[name].get("city") or None,
            "shop_url": first[name]["shop_url"],
            "origin_type": first[name]["origin_type"],
            "products": n,
        }
        for name, n in counts.most_common()
    ]


async def product(product_id: str) -> dict | None:
    if not knowledge_base_ready():
        return None
    for p in (await get_agent()).catalogue.products:
        if p["product_id"] == product_id:
            return p
    return None
