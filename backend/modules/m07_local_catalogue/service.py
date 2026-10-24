"""Real implementation of M7: one shared LocalShopAgent (catalogue + FashionCLIP loaded once).

The knowledge base lives in ml/data/shops/ (DVC, not git). On a clone without it, every function
answers with mock.py's fixed data instead of failing, so the modules that call M7 are never blocked.
"""

import logging
import time
from collections import Counter

from . import events, mock
from .agent import LocalShopAgent
from .contract import LocalPiecesInput, OutfitsInput
from .memory import ANONYMOUS, AgentMemory
from .paths import CATALOGUE_CSV

log = logging.getLogger("m07.service")
_agent: LocalShopAgent | None = None
_memory: AgentMemory | None = None


def knowledge_base_ready() -> bool:
    return CATALOGUE_CSV.is_file()


def memory() -> AgentMemory:
    """The agent's memory; history / feedback / forget use it without loading the catalogue."""
    global _memory
    if _memory is None:
        _memory = AgentMemory()
    return _memory


async def get_agent() -> LocalShopAgent:
    """The agent used by the API and the orchestrator tool; loads the knowledge base on first use."""
    global _agent
    if _agent is None:
        _agent = LocalShopAgent(memory=memory())
    if _agent.catalogue is None:
        await _agent.setup()
    return _agent


async def search(req: dict, channel: str = "api") -> dict:
    """LocalShopInput (dict) -> LocalShopOutput (dict). Raises AgentError / ValidationError on bad input.

    Every real search is written to the event log (events.py) and gets a `search_id`, which the app sends
    back with its clicks. Mock answers are not logged.
    """
    if not knowledge_base_ready():
        log.warning("M7 knowledge base %s missing: serving mock.py (dvc pull or rebuild it)", CATALOGUE_CSV)
        return mock.search(req)
    started = time.perf_counter()
    agent = await get_agent()
    out = await agent(req)
    logged = req
    if req.get("answer") or req.get("next_page"):  # log the search actually run, restored from memory
        session = agent.memory.session(req.get("user_id") or ANONYMOUS, out["session_id"])
        logged = session.get("request") or req
    out["search_id"] = events.log_search(logged, out, 1000 * (time.perf_counter() - started), channel)
    return out


async def outfits(req: dict) -> dict:
    """OutfitsInput (dict) -> OutfitsOutput (dict): outfits from the user's wardrobe around a local piece."""
    if not knowledge_base_ready():
        return mock.outfits(req)
    agent = await get_agent()
    return (await agent.outfits(OutfitsInput.model_validate(req))).model_dump(mode="json")


async def local_pieces(req: dict) -> dict:
    """LocalPiecesInput (dict) -> LocalPiecesOutput (dict): Tunisian pieces for an outfit of the day."""
    if not knowledge_base_ready():
        return mock.local_pieces(req)
    agent = await get_agent()
    return (await agent.local_pieces(LocalPiecesInput.model_validate(req))).model_dump(mode="json")


def feedback(user_id: str, decision_id: str, useful: bool | None, bought_product_id: str | None) -> dict:
    """Were the results useful / was one bought? -> long-term memory. Unknown decision -> ValueError."""
    found = memory().feedback(user_id, decision_id, useful, bought_product_id)
    if found is None:
        raise ValueError(f"unknown decision {decision_id}")
    return found


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
