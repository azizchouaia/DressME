"""BO5 Smart Buy agent: photo of a candidate piece -> BUY / THINK / SKIP.

1. facts()  : ask the other modules (M1 similar items, M2 outfits, M5 gaps) — once.
2. decide() : rules or learned model, optional personal strictness (bandit).
3. extras   : uncertainty question, what-if, XAI contributions, wear prediction, size, buy links.
"""

import json
from pathlib import Path

import yaml

from shared.base_agent import BaseAgent

from modules.m13_partner_links import service as partners
from modules.m18_size_fit import service as sizefit
from .bandit import PersonalThresholds
from .clients import get_clients
from .contract import SmartBuyInput, SmartBuyOutput
from .pipeline import gap, redundancy, score, uncertainty, unlock, wear, whatif
from .pipeline.decide import NAMES, decide

HERE = Path(__file__).resolve().parent
CONFIG = yaml.safe_load((HERE / "config.yaml").read_text())
MODEL_FILE = HERE / "models" / "verdict_model.json"


class SmartBuyAgent(BaseAgent[SmartBuyInput, SmartBuyOutput]):
    name = "smartbuy"
    description = ("Judge whether a piece the user wants to buy duplicates their wardrobe, how many new "
                   "outfits it unlocks, and answer buy / think / skip with size advice and local buy links.")
    input_model = SmartBuyInput
    output_model = SmartBuyOutput

    def __init__(self, config: dict | None = None):
        super().__init__(config or CONFIG)
        self.clients = get_clients(self.config["use_mocks"], self.config.get("dataset", "synthetic"))
        data_dir = (HERE.parent.parent / self.config["data_dir"]).resolve()
        self.charts = sizefit.load_charts(data_dir)
        self.shops = partners.load(data_dir)
        self.typical = partners.typical_prices(self.shops)   # usual price per type, from local shops
        self.model = None
        if self.config.get("decision") == "learned" and MODEL_FILE.exists():
            self.model = json.loads(MODEL_FILE.read_text())
        self.bandit = PersonalThresholds() if self.config.get("personalize") else None

    @staticmethod
    def _label(k: str, value, contrib: float) -> str:
        """Readable name for an XAI contribution (says what the piece IS, not the raw feature)."""
        if k == "duplicate":
            return "you already own it" if value else "not a duplicate"
        if k == "same_type":
            return "you own many of this type" if contrib < 0 else "you own few of this type"
        if k == "gap_fill":
            return "fills a gap" if value else "no gap to fill"
        if k == "fair_price":
            return "fair price for this type" if contrib >= 0 else "pricey for this type"
        if k == "price_value":
            return "good price per outfit" if contrib >= 0 else "high price per outfit"
        if k == "new_outfits":
            return "creates many outfits" if contrib >= 0 else "creates few outfits"
        if k == "novelty":
            return "new to your wardrobe" if contrib >= 0 else "close to what you own"
        return NAMES.get(k, k)

    async def facts(self, image: str, user_id: str, price: float | None, need_for_occasion: bool | None = None) -> dict:
        cfg, cl = self.config, self.clients
        cand = cl.classify(image)                                                     # M1
        cand.setdefault("id", Path(image).stem)
        neigh = cl.similar(user_id, cand["embedding"], max(cfg["top_k_neighbours"], 10))  # M1
        red = redundancy.check(neigh[: cfg["top_k_neighbours"]], cand, cfg)
        g = gap.fill(cl.gaps(user_id), cand["subcategory"], cand["colour"])         # M5
        if not g and need_for_occasion:
            g = "needed for an occasion"
        return {"cand": cand, "subcategory": cand["subcategory"], "colour": cand["colour"], "neigh": neigh,
                "red": red, "n_same": cl.count_type(user_id, cand["subcategory"]),  # M1
                "unl": unlock.count(cl.recommend_with(user_id, cand)),             # M2
                "gap": g, "price": price, "typical_price": self.typical.get(cand["subcategory"])}

    async def run(self, inp: SmartBuyInput) -> SmartBuyOutput:
        cfg, cl = self.config, self.clients
        f = await self.facts(inp.probe_image, inp.user_id, inp.price_tnd, inp.need_for_occasion)
        cand, red, unl, g, n_same = f["cand"], f["red"], f["unl"], f["gap"], f["n_same"]

        offset = self.bandit.choose(inp.user_id) if self.bandit else 0               # idea 9
        d = decide(f, cfg, self.model, offset)                                       # idea 4
        v = d["verdict"]

        rs = score.reasons(red, unl, g, d["cost_per_outfit"], lambda n: n["label"], n_same, cand["subcategory"], cfg)
        items = {i["id"]: i for i in getattr(cl, "wardrobes", {}).get(inp.user_id, {}).get("items", [])}
        wp = wear.predict(f["neigh"], items, cand["category"], inp.price_tnd)          # idea 5
        typ = f["typical_price"]
        if typ and inp.price_tnd and inp.price_tnd > typ * 1.3:
            rs.append(f"expensive for a {cand['subcategory']}: usually about {round(typ)} TND in local shops")
        if wp["predicted_wears"] is not None:
            cpw = f" -> {wp['cost_per_wear']} TND per wear" if wp["cost_per_wear"] else ""
            rs.append(f"you'd wear it about {wp['predicted_wears']} times a year (like your similar pieces){cpw}")
        unc = uncertainty.check(d, f, cfg, inp.ai_confidence)                        # idea 3
        wi = whatif.explain(f, cfg, self.model, offset, v)                           # idea 8
        contrib = {self._label(k, d["features"].get(k), x): x                                  # idea 7
                   for k, x in sorted(d["contributions"].items(), key=lambda kv: -abs(kv[1])) if abs(x) >= 0.5}

        expl = cl.explain({"verdict": v, "reasons": rs, "candidate": cand["label"]})  # M8
        size = sizefit.advise(self.charts, inp.shop_brand, cand["category"],
                              inp.body.model_dump() if inp.body else None)            # M18
        links = partners.links(self.shops, cand["subcategory"], cand["colour"], inp.price_tnd) if v != "skip" else []  # M13
        return SmartBuyOutput(
            verdict=v, score=d["score"], breakdown=d["breakdown"], category=cand["category"],
            is_duplicate=red["is_duplicate"],
            similar_items=[{"item_id": n["item_id"], "label": n["label"], "similarity": n["similarity"]} for n in red["similar"]],
            new_outfits=unl["new_outfits"], pairs_with=unl["pairs_with"], fills_gap=g,
            cost_per_outfit_tnd=d["cost_per_outfit"], reasons=rs, explanation=expl,
            size_advice=size, buy_links=links,
            decision_mode="learned" if self.model else "rules", probabilities=d["probabilities"],
            contributions=contrib, what_if=wi, uncertain=unc["uncertain"], question=unc["question"],
            question_key=unc["question_key"], predicted_wears=wp["predicted_wears"],
            cost_per_wear_tnd=wp["cost_per_wear"], threshold_offset=offset,
        )
