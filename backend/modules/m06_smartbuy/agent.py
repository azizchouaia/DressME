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
from .contract import AgentInfo, Body, NextAction, SmartBuyInput, SmartBuyOutput
from .identity import CARD, VERSION, tool_description
from .memory import AgentMemory
from . import explainer
from . import goals as goals_mod
from .pipeline import gap, redundancy, score, uncertainty, unlock, wear, whatif
from .pipeline.decide import NAMES, decide

HERE = Path(__file__).resolve().parent
CONFIG = yaml.safe_load((HERE / "config.yaml").read_text())
MODEL_FILE = HERE / "models" / "verdict_model.json"


class SmartBuyAgent(BaseAgent[SmartBuyInput, SmartBuyOutput]):
    name = CARD["name"]
    version = VERSION
    description = tool_description()
    input_model = SmartBuyInput
    output_model = SmartBuyOutput

    def __init__(self, config: dict | None = None, memory: AgentMemory | None = None):
        super().__init__(config or CONFIG)
        self.memory = memory or AgentMemory()
        self.clients = get_clients(self.config["use_mocks"], self.config.get("dataset", "synthetic"),
                                   self.config.get("real") or [])
        data_dir = (HERE.parent.parent / self.config["data_dir"]).resolve()
        self.charts = sizefit.load_charts(data_dir)
        self.shops = partners.load(data_dir, self.config.get("shops_source", "auto"))
        # usual price per type: real local shops (M7) first, fictional shops for the types they lack
        self.typical = {**partners.typical_prices(partners.load(data_dir, "fictional")),
                        **partners.typical_prices(self.shops)}
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
        if k == "over_budget":
            return "over your monthly budget"
        if k == "goal_fit":
            return "fits your goals" if contrib >= 0 else "goes against your goals"
        if k == "novelty":
            return "new to your wardrobe" if contrib >= 0 else "close to what you own"
        return NAMES.get(k, k)

    async def facts(self, image: str, user_id: str, price: float | None, need_for_occasion: bool | None = None) -> dict:
        cfg, cl = self.config, self.clients
        if hasattr(cl, "sources"):
            cl.sources.clear()  # which module answered, for this request only
        cand = cl.classify(image)                                                     # M1
        cand.setdefault("id", Path(image).stem)
        neigh = cl.similar(user_id, cand["embedding"], max(cfg["top_k_neighbours"], 10))  # M1
        red = redundancy.check(neigh[: cfg["top_k_neighbours"]], cand, cfg)
        g = gap.fill(cl.gaps(user_id), cand["subcategory"], cand["colour"])         # M5
        if not g and need_for_occasion:
            g = "needed for an occasion"
        user_goals = cl.goals(user_id)                                               # M5 (mock)
        gf = goals_mod.goal_fit(user_goals, cl.items(user_id), cand, price)
        return {"cand": cand, "subcategory": cand["subcategory"], "colour": cand["colour"], "neigh": neigh,
                "red": red, "n_same": cl.count_type(user_id, cand["subcategory"]),  # M1
                "unl": unlock.count(cl.recommend_with(user_id, cand)),             # M2
                "gap": g, "price": price, "typical_price": self.typical.get(cand["subcategory"]),
                "goal": gf, "goals": user_goals}

    # ------------------------------------------------------------------ agent loop with memory
    def card(self) -> dict:
        return CARD

    async def run(self, inp: SmartBuyInput) -> SmartBuyOutput:
        """judge (photo) or answer (to the last question): memory in, decision, memory out, next actions."""
        uid, sid, notes, answering = inp.user_id, inp.session_id, [], inp.answer is not None
        if inp.answer:
            s = self.memory.session(uid, sid)
            if not s or not s.get("question"):
                raise ValueError("nothing to answer: no open Smart Buy question in this session")
            req = dict(s["request"])
            key, val = inp.answer.question_key, inp.answer.value
            if key == "need_for_occasion":
                req["need_for_occasion"] = val in (True, "yes", "true", "oui", "ey")
            elif key == "confirm_type":
                if val in (False, "no", "non", "le"):
                    raise ValueError("photo not confirmed: please send a clearer photo")
                req["ai_confidence"] = 1.0
            notes.append(f"used your answer to: {s.get('question')}")
            inp = SmartBuyInput.model_validate({**req, "session_id": sid, "language": inp.language})
        if not inp.probe_image:
            raise ValueError("send a photo (probe_image) or an answer")
        if inp.body and inp.body.fit_text:  # free text -> fit facts (rules, LLM if needed)
            from modules.m18_size_fit import text_fit
            brands = [b for b in self.charts if not b.startswith("_")]
            parsed = text_fit.parse(inp.body.fit_text, brands, self.config.get("fit_text_llm", True))
            known = {(r["brand"], r["size"]) for r in inp.body.fit_refs}
            refs = list(inp.body.fit_refs) + [r for r in parsed["refs"] if (r["brand"], r["size"]) not in known]
            like = parsed["like_fit"] if inp.body.like_fit == "normal" and parsed["like_fit"] else inp.body.like_fit
            inp = inp.model_copy(update={"body": inp.body.model_copy(update={"fit_refs": refs, "like_fit": like})})
            got = "; ".join(f"{r['brand']} {r['size']} {r['fit'].replace('_', ' ')}" for r in parsed["refs"])
            notes.append(f"read from your text ({parsed['method']}): {got or 'nothing clear'}"
                         + (f", you like it {like}" if parsed["like_fit"] else ""))
            notes += text_fit.part_tips(parsed["refs"])
        prefs = self.memory.preferences(uid)
        if inp.body and (inp.body.fit_refs or inp.body.like_fit != "normal" or inp.body.chest_cm or inp.body.waist_cm):
            self.memory.set_preferences(uid, body=inp.body.model_dump())
        elif prefs.get("body"):
            inp = inp.model_copy(update={"body": Body(**prefs["body"])})
            notes.append("used your saved body / fit info for the size")

        out = await self._judge(inp)

        before = self.memory.same_piece_before(uid, out.piece)
        if before and not answering:
            fb = before.get("feedback") or {}
            extra = " and you bought it" if fb.get("bought") else ""
            notes.append(f"you asked about a {out.piece.lower()} before ({before['at']}): {before['verdict'].upper()}{extra}")
        out.decision_id = self.memory.remember(uid, sid, inp.model_dump(mode="json", exclude={"answer"}),
                                               out.model_dump())
        out.agent, out.session_id, out.memory_notes = AgentInfo(name=self.name, version=self.version), sid, notes
        out.next_actions = self._next_actions(out, inp)
        return out

    def _next_actions(self, out: SmartBuyOutput, inp: SmartBuyInput) -> list[NextAction]:
        acts = []
        if out.uncertain and out.question:
            acts.append(NextAction(action="ask_user", label=out.question, tool="smartbuy",
                                   args={"session_id": out.session_id, "answer": {"question_key": out.question_key}}
                                   if out.question_key else {}))
        if out.verdict == "buy":
            if out.buy_links:
                acts.append(NextAction(action="open_shop", label=f"Buy it at {out.buy_links[0].shop}", tool=None,
                                       args={"url": out.buy_links[0].url, "product_id": out.buy_links[0].product_id, "shop": out.buy_links[0].shop}))
            acts.append(NextAction(action="show_outfits", label="See outfits with this piece", tool="stylist",
                                   args={"endpoint": "/m02/complete", "pinned": out.piece}))
        elif out.verdict == "think":
            acts.append(NextAction(action="find_cheaper", label="Find it cheaper in local shops", tool="localshop",
                                   args={"subcategory": None, "max_price_tnd": round((inp.price_tnd or 0) * 0.8) or None,
                                         "query": out.piece}))
        else:
            if out.similar_items:
                acts.append(NextAction(action="show_outfits", label=f"Style your {out.similar_items[0].label.lower()} instead",
                                       tool="stylist", args={"endpoint": "/m02/complete",
                                                         "pinned_item_ids": [out.similar_items[0].item_id]}))
            if out.fills_gap is None:
                acts.append(NextAction(action="find_alternative", label="Find a piece that fills a real gap",
                                       tool="smartbuy", args={"endpoint": "/m06/shopping-list", "user_id": inp.user_id}))
        acts.append(NextAction(action="feedback", label="Did you buy it? Was the advice good?", tool="smartbuy",
                               args={"endpoint": "/m06/feedback", "decision_id": out.decision_id}))
        return acts

    def feedback(self, user_id: str, decision_id: str, bought: bool | None = None, liked: bool | None = None) -> dict:
        """Long-term memory + personal strictness (bandit): was the advice good?"""
        h = self.memory.feedback(user_id, decision_id, bought, liked)
        if h is None:
            raise ValueError(f"unknown decision {decision_id}")
        if self.bandit and liked is not None:
            self.bandit.update(user_id, h.get("offset", 0), liked)
        return h

    async def _judge(self, inp: SmartBuyInput) -> SmartBuyOutput:
        cfg, cl = self.config, self.clients
        f = await self.facts(inp.probe_image, inp.user_id, inp.price_tnd, inp.need_for_occasion)
        cand, red, unl, g, n_same = f["cand"], f["red"], f["unl"], f["gap"], f["n_same"]

        offset = self.bandit.choose(inp.user_id) if self.bandit else 0               # idea 9
        d = decide(f, cfg, self.model, offset)                                       # idea 4
        v = d["verdict"]

        rs = score.reasons(red, unl, g, d["cost_per_outfit"], lambda n: n["label"], n_same, cand["subcategory"], cfg)
        items = {i["id"]: i for i in getattr(cl, "wardrobes", {}).get(inp.user_id, {}).get("items", [])}
        wp = wear.predict(f["neigh"], items, cand["category"], inp.price_tnd)          # idea 5
        rs = f["goal"]["reasons"][:2] + rs                                           # goals first: the user chose them
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

        mode = cfg.get("explainer", "own")                                            # own (Ollama) | m8 | template
        if mode == "m8":
            expl, expl_src = cl.explain({"verdict": v, "reasons": rs, "candidate": cand["label"]}), "m8"
        else:
            expl, expl_src = explainer.explain(v, cand["label"], rs, inp.price_tnd, inp.language, mode,
                                               cfg.get("explainer_timeout", 20))
        size = sizefit.advise(self.charts, inp.shop_brand, cand["category"],
                              inp.body.model_dump() if inp.body else None)            # M18
        links = []
        if v != "skip":  # M7 search (same look as the photo, or type + colour), else M13's shop list
            links = cl.catalogue_search(cand["subcategory"], cand["colour"], inp.price_tnd,
                                        embedding=cand.get("embedding")) if hasattr(cl, "sources") else []
            links = links or partners.links(self.shops, cand["subcategory"], cand["colour"], inp.price_tnd,
                                            one_per_shop=True)
        return SmartBuyOutput(
            verdict=v, score=d["score"], breakdown=d["breakdown"], category=cand["category"],
            is_duplicate=red["is_duplicate"],
            similar_items=[{"item_id": n["item_id"], "label": n["label"], "similarity": n["similarity"]} for n in red["similar"]],
            new_outfits=unl["new_outfits"], pairs_with=unl["pairs_with"], fills_gap=g,
            cost_per_outfit_tnd=d["cost_per_outfit"], reasons=rs, explanation=expl,
            size_advice=size, buy_links=links, sources={**getattr(cl, "sources", {}), "explanation": expl_src}, piece=cand["label"],
            decision_mode="learned" if self.model else "rules", probabilities=d["probabilities"],
            contributions=contrib, uncertain=unc["uncertain"],
            # `question` = something the user can ANSWER (the orchestrator stops and asks it); a tip is a what-if line
            question=unc["question"] if unc["question_key"] else None,
            what_if=wi + ([unc["question"]] if unc["question"] and not unc["question_key"] else []),
            question_key=unc["question_key"], predicted_wears=wp["predicted_wears"],
            cost_per_wear_tnd=wp["cost_per_wear"], threshold_offset=offset,
            goal_fit=round(f["goal"]["score"], 2) if f["goals"].get("templates") else None,
            fills_goal=f["goal"]["fills"], goals=f["goals"].get("templates", []),
        )
