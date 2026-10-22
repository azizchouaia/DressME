"""BO6 agent `localshop`: memory in, search (M7), memory out, question + next_actions for the orchestrator."""

import re

import numpy as np

from shared.base_agent import AgentError, BaseAgent

from . import clients
from .contract import AgentInfo, LocalShopInput, LocalShopOutput, NextAction, ParsedQuery, ShopResult
from .identity import CARD, VERSION, tool_description
from .llm import get_llm
from .memory import ANONYMOUS, AgentMemory
from .paths import CATALOGUE_CSV, CONFIG, INDEX_DIR, model_source
from .pipeline import filter, parse, rerank, retrieve, understand
from .pipeline.catalogue import Catalogue
from .scraper.normalize import fold
from .taxonomy import SUBCATEGORIES, canonical_city, colour_name, governorate, label

# Questions, labels and memory notes in the request's language. Facts (shops, prices, notes) stay as found.
TEXTS = {
    "fr": {
        "gender": "Pour femme ou pour homme ?",
        "budget": "Rien à moins de {max:g} TND (le moins cher : {cheapest:g} TND). "
        "Quel budget maximum en TND ?",
        "query": "Quel type de pièce cherches-tu ? (robe, baskets, sac...)",
        "open_shop": "Voir chez {shop}",
        "judge": "Est-ce un bon achat pour moi ?",
        "outfits": "Des tenues avec cette pièce",
        "more": "Voir plus de résultats",
        "feedback": "Ces résultats t'ont été utiles ?",
        "gender_memory": "Pièces pour {gender} : ta réponse précédente est gardée en mémoire.",
        "answer": "Ta réponse « {answer} » est appliquée à ta recherche précédente.",
        "more_memory": "Suite de ta recherche précédente.",
        "women": "femme",
        "men": "homme",
    },
    "en": {
        "gender": "For women or for men?",
        "budget": "Nothing under {max:g} TND (cheapest: {cheapest:g} TND). "
        "What is your maximum budget in TND?",
        "query": "What kind of piece are you looking for? (dress, sneakers, bag...)",
        "open_shop": "See it at {shop}",
        "judge": "Is it a good buy for me?",
        "outfits": "Outfits with this piece",
        "more": "Show more results",
        "feedback": "Were these results useful?",
        "gender_memory": "Pieces for {gender}: your previous answer is remembered.",
        "answer": "Your answer “{answer}” is applied to your previous search.",
        "more_memory": "More results of your previous search.",
        "women": "women",
        "men": "men",
    },
    "ar": {
        "gender": "للنساء أم للرجال؟",
        "budget": "لا شيء بأقل من {max:g} دينار (الأرخص: {cheapest:g} دينار). "
        "ما هي ميزانيتك القصوى بالدينار؟",
        "query": "ما نوع القطعة التي تبحث عنها؟ (فستان، حذاء رياضي، حقيبة...)",
        "open_shop": "عرض في {shop}",
        "judge": "هل هي شراء جيد لي؟",
        "outfits": "إطلالات مع هذه القطعة",
        "more": "عرض نتائج أخرى",
        "feedback": "هل كانت هذه النتائج مفيدة؟",
        "gender_memory": "قطع {gender}: تم تذكر إجابتك السابقة.",
        "answer": "تم تطبيق إجابتك «{answer}» على بحثك السابق.",
        "more_memory": "تتمة بحثك السابق.",
        "women": "للنساء",
        "men": "للرجال",
    },
}

# Answers to "for women or for men?" (FR / EN / darija / Arabic), compared after fold().
_WOMEN = {
    "femme",
    "femmes",
    "f",
    "women",
    "woman",
    "w",
    "fille",
    "filles",
    "dame",
    "dames",
    "mra",
    "nsa",
    "bnet",
    "امراة",
    "نساء",
    "النساء",
    "للنساء",
    "بنات",
}
_MEN = {
    "homme",
    "hommes",
    "h",
    "men",
    "man",
    "m",
    "garcon",
    "garcons",
    "rajel",
    "rjel",
    "rjal",
    "رجل",
    "رجال",
    "الرجال",
    "للرجال",
}
_ANY = {"les deux", "both", "unisex", "unisexe", "mixte", "peu importe", "any", "zouz", "الاثنين", "كلاهما"}
_FOR = re.compile(r"^(?:pour|for|lel)\s+")  # "pour femme" -> "femme" ("les deux" keeps its "l")

# Fields of one conversation turn, not of the search itself (never stored as the request).
_TURN_FIELDS = {"session_id", "language", "answer", "next_page"}


def gender_answer(value: str) -> str | None:
    """'femme' / 'pour homme' / 'rajel' / 'les deux' -> women / men / any; None when not understood."""
    text = _FOR.sub("", fold(value).strip(" .!?"))
    if text in _ANY:
        return "any"
    if text in _WOMEN:
        return "women"
    if text in _MEN:
        return "men"
    return parse.gender_from_query(fold(value))


# Notes on the search, in the request's language (Arabic keeps French for now).
NOTES = {
    "fr": {
        "no_style": "Vecteur de style « {style} » pas encore disponible (M5) : classement sans le style.",
        "other_cities": "Rien trouvé à {city} : résultats d'autres villes ou de boutiques en ligne.",
        "sold_out": "Aucun article en stock pour l'instant : {n} article(s) en rupture de stock, "
        "à vérifier auprès de la boutique.",
        "no_colour": "Aucun article de couleur {colour} parmi les {what}{where} : "
        "voici les autres {what} disponibles.",
        "in_city": " à {city}",
        "items": "articles",
        "nothing_for": "Je n'ai trouvé aucun article correspondant à « {asked} » dans les boutiques locales.",
        "no_match": "Aucun article ne correspond à ces critères.",
        "llm_note": "Demande comprise avec l'IA ({model}) : {what}.",
        "rewritten": "requête reformulée",
    },
    "en": {
        "no_style": "Style vector “{style}” not available yet (M5): ranked without the style.",
        "other_cities": "Nothing found in {city}: results from other cities or online shops.",
        "sold_out": "Nothing in stock for now: {n} piece(s) sold out, to check with the shop.",
        "no_colour": "No {colour} piece among the {what}{where}: here are the other {what} available.",
        "in_city": " in {city}",
        "items": "pieces",
        "nothing_for": "I found no piece matching “{asked}” in the local shops.",
        "no_match": "No piece matches these criteria.",
        "llm_note": "Request understood with AI ({model}): {what}.",
        "rewritten": "request rewritten",
    },
}


def notes_for(language: str) -> dict:
    return NOTES.get(language, NOTES["fr"])


class LocalShopAgent(BaseAgent[LocalShopInput, LocalShopOutput]):
    name = CARD["name"]
    description = tool_description()
    input_model = LocalShopInput
    output_model = LocalShopOutput
    is_async_job = False

    def __init__(
        self,
        config: dict | None = None,
        catalogue: Catalogue | None = None,
        encoder=None,
        memory: AgentMemory | None = None,
    ):
        super().__init__(config or CONFIG)
        # Heavy objects are created in setup() (or injected by tests), never at import time.
        self.catalogue = catalogue
        self.encoder = encoder
        self.memory = memory or AgentMemory()

    def card(self) -> dict:
        return CARD

    async def setup(self) -> None:
        if self.catalogue is None:
            self.catalogue = Catalogue.load(CATALOGUE_CSV, INDEX_DIR, self.config["embedding_dim"])
        if self.encoder is None and self.catalogue.has_embedding.any():
            from .pipeline.encoder import FashionCLIP

            self.encoder = FashionCLIP(model_source())

    def _vector(self, values: list[float] | None, what: str) -> np.ndarray | None:
        if values is None:
            return None
        vec = np.asarray(values, dtype=np.float32)
        if vec.shape != (self.config["embedding_dim"],):
            raise AgentError(f"{what} must have {self.config['embedding_dim']} values (FashionCLIP space)")
        return vec / max(float(np.linalg.norm(vec)), 1e-12)

    def _parsed(self, inp: LocalShopInput, remembered_gender: str | None = None) -> tuple[ParsedQuery, bool]:
        """How the request is understood; True when the gender comes from the user's memory."""
        vocabulary = parse.KEYWORDS | (self.catalogue.vocabulary if self.catalogue is not None else set())
        parsed = parse.parse(inp.query, inp.gap, vocabulary)
        # Explicit fields from the caller win over what was read in the text.
        if inp.subcategory:
            if inp.subcategory not in SUBCATEGORIES:
                raise AgentError(f"unknown subcategory {inp.subcategory!r}")
            parsed.subcategory, parsed.category = inp.subcategory, SUBCATEGORIES[inp.subcategory][0]
        elif inp.category:
            parsed.category, parsed.subcategory = inp.category.value, None
        if inp.color:
            parsed.color = parse.normalize_color(inp.color)
        if inp.gender:
            parsed.gender = inp.gender
        if inp.max_price_tnd is not None:
            parsed.max_price_tnd = inp.max_price_tnd
        if inp.min_price_tnd is not None:
            parsed.min_price_tnd = inp.min_price_tnd
        if inp.city:
            parsed.city = canonical_city(inp.city) or inp.city.strip()
            parsed.governorate = governorate(parsed.city)
        # Nothing said about gender (text or field): the user's earlier answer, kept in memory.
        from_memory = parsed.gender is None and remembered_gender is not None
        if from_memory:
            # Only for a type of piece this gender really wears here (a man looking at dresses: a gift).
            cat = self.catalogue
            kind = filter.run(cat, parsed, include_unavailable=True, use_city=False, use_color=False)
            known = kind & np.isin(cat.gender, ["women", "men", "unisex"])
            share = (known & (cat.gender == remembered_gender)).sum() / max(int(known.sum()), 1)
            if share >= self.config["memory_gender_min_share"]:
                parsed.gender = remembered_gender
            else:
                from_memory = False
        # The prompt follows the final slots, so calls with explicit fields only also use FashionCLIP.
        parsed.prompt_en = parse.build_prompt(parsed, " ".join(t for t in (inp.query, inp.gap) if t))
        return parsed, from_memory

    @staticmethod
    def _area(product: dict, parsed: ParsedQuery, city_applied: bool) -> str | None:
        """Shop cities; for a chain under a city filter, only the cities that matched (not its first one)."""
        cities = [c for c in (product.get("city") or "").split("; ") if c]
        if city_applied:
            local = [c for c in cities if c == parsed.city or governorate(c) == parsed.governorate]
            if local:
                return "; ".join(local)
        return "; ".join(cities) or None

    @staticmethod
    def _colour_note(parsed: ParsedQuery, city_applied: bool, language: str) -> str:
        """The colour asked for exists nowhere (in stock or not, in any city): say it before other colours."""
        t = notes_for(language)
        what = label(parsed.subcategory, language).lower() if parsed.subcategory else t["items"]
        where = t["in_city"].format(city=parsed.city) if city_applied else ""
        return t["no_colour"].format(colour=colour_name(parsed.color, language), what=what, where=where)

    # ------------------------------------------------------------------ agent loop with memory
    async def run(self, inp: LocalShopInput) -> LocalShopOutput:
        """search, answer (to the last question) or next page: memory in, search, memory out, next actions."""
        if self.catalogue is None:
            await self.setup()
        uid = inp.user_id or ANONYMOUS
        texts = TEXTS[inp.language]
        memory_notes: list[str] = []
        if inp.answer or inp.next_page:
            request = self._restore(inp, uid, memory_notes)
        else:
            request = inp.model_dump(mode="json", exclude=_TURN_FIELDS)
        search = LocalShopInput.model_validate({**request, "language": inp.language})

        remembered = self.memory.preferences(uid).get("gender")  # women / men / any (= do not ask again)
        gender = remembered if remembered in ("women", "men") else None
        out = await self._search(search, gender, memory_notes)
        if self._llm_can_help(search, out):
            slots = await understand.run(get_llm(), search.query)
            if slots:  # the normal search runs again on what the LLM read, checked against the catalogue
                retry = search.model_copy(update=slots)
                second = await self._search(retry, gender, [])
                if second.results:
                    request |= slots  # memory keeps the understood request (answer, next page)
                    search, out = retry, second
                    out.parsed.understood_by = "llm"
                    note = notes_for(inp.language)["llm_note"].format(
                        model=get_llm().model, what=self._describe(out.parsed, inp.language)
                    )
                    out.note = f"{out.note} {note}" if out.note else note
        if search.offset == 0:
            out.question, out.question_key = self._question(search, out, ask_gender=remembered is None)

        out.agent = AgentInfo(name=self.name, version=VERSION)
        out.session_id = inp.session_id
        out.decision_id = self.memory.remember(uid, inp.session_id, request, out.model_dump(mode="json"))
        out.memory_notes = memory_notes
        out.next_actions = self._next_actions(out, search, texts)
        return out

    @staticmethod
    def _llm_can_help(inp: LocalShopInput, out: LocalShopOutput) -> bool:
        """Only for a written request where the rules understood no piece, colour or photo."""
        parsed = out.parsed
        understood = parsed.subcategory or parsed.category or parsed.color or inp.image_embedding
        return bool(inp.query.strip()) and not understood and get_llm().on("understand")

    @staticmethod
    def _describe(parsed: ParsedQuery, language: str) -> str:
        parts = [
            label(parsed.subcategory, language) if parsed.subcategory else None,
            colour_name(parsed.color, language) if parsed.color else None,
            f"≤ {parsed.max_price_tnd:g} TND" if parsed.max_price_tnd else None,
            parsed.city,
        ]
        return ", ".join(p for p in parts if p) or notes_for(language)["rewritten"]

    def _restore(self, inp: LocalShopInput, uid: str, memory_notes: list[str]) -> dict:
        """The last search of this session, with the user's answer applied or moved to the next page."""
        session = self.memory.session(uid, inp.session_id)
        if not session.get("request"):
            raise AgentError("nothing to continue: no earlier localshop search in this session")
        request = dict(session["request"])
        texts = TEXTS[inp.language]
        if inp.answer:
            key = inp.answer.question_key or session.get("question_key")
            if not key:
                raise AgentError("nothing to answer: no open localshop question in this session")
            self._apply_answer(request, key, inp.answer.value, uid)
            request["offset"] = 0
            memory_notes.append(texts["answer"].format(answer=inp.answer.value))
        else:
            request["offset"] = request.get("offset", 0) + request.get("k", self.config["top_k"])
            memory_notes.append(texts["more_memory"])
        return request

    def _apply_answer(self, request: dict, key: str, value: str, uid: str) -> None:
        if key == "gender":
            gender = gender_answer(value)
            if gender is None:
                raise AgentError(f"answer {value!r} not understood: say 'femme', 'homme' or 'les deux'")
            request["gender"] = None if gender == "any" else gender
            self.memory.set_preferences(uid, gender=gender)  # not asked again; forgotten with DELETE /memory
        elif key == "max_price_tnd":
            folded = fold(value)
            _, high = parse.parse_price(folded)
            if high is None and (number := re.search(r"\d+(?:[.,]\d+)?", folded)):
                high = float(number.group().replace(",", "."))
            if not high:
                raise AgentError(f"answer {value!r} not understood: give a budget in TND, e.g. '150'")
            request["max_price_tnd"] = high
        elif key == "query":
            request["query"] = " ".join(t for t in (request.get("query"), value.strip()) if t)
        else:
            raise AgentError(f"unknown question_key {key!r}")

    def _question(
        self, inp: LocalShopInput, out: LocalShopOutput, ask_gender: bool
    ) -> tuple[str | None, str | None]:
        """ONE question the user can answer, only when the answer changes the results."""
        texts, parsed = TEXTS[inp.language], out.parsed
        if not out.results:
            understood = parsed.subcategory or parsed.category or parsed.color or inp.image_embedding
            if not understood:
                return texts["query"], "query"
            if parsed.max_price_tnd is not None:
                cheapest = self._cheapest_without_budget(parsed)
                if cheapest is not None and cheapest > parsed.max_price_tnd:
                    question = texts["budget"].format(max=parsed.max_price_tnd, cheapest=cheapest)
                    return question, "max_price_tnd"
            return None, None
        # Results for both women and men while the user said neither: worth one question.
        if ask_gender and parsed.gender is None and parsed.category != "accessory":
            if {"women", "men"} <= {r.gender for r in out.results}:
                return texts["gender"], "gender"
        return None, None

    def _cheapest_without_budget(self, parsed: ParsedQuery) -> float | None:
        relaxed = parsed.model_copy(update={"max_price_tnd": None, "min_price_tnd": None})
        prices = self.catalogue.price[filter.run(self.catalogue, relaxed, use_city=False)]
        prices = prices[~np.isnan(prices)]
        return float(prices.min()) if len(prices) else None

    def _next_actions(self, out: LocalShopOutput, inp: LocalShopInput, texts: dict) -> list[NextAction]:
        acts = []
        if out.question:
            acts.append(
                NextAction(
                    action="ask_user",
                    label=out.question,
                    tool=self.name,
                    args={"session_id": out.session_id, "answer": {"question_key": out.question_key}},
                )
            )
        if out.results:
            top = out.results[0]
            acts.append(
                NextAction(
                    action="open_shop",
                    label=texts["open_shop"].format(shop=top.shop),
                    args={
                        "url": top.product_url,
                        "product_id": top.product_id,
                        "rank": 1,
                        "events_endpoint": "/m07/events",
                    },
                )
            )
            if top.price_tnd is not None:
                acts.append(
                    NextAction(
                        action="judge",
                        label=texts["judge"],
                        tool="smartbuy",
                        args={
                            "probe_image": top.image_url,
                            "price_tnd": top.price_tnd,
                            "shop_brand": top.shop,
                        },
                    )
                )
            acts.append(
                NextAction(
                    action="show_outfits",
                    label=texts["outfits"],
                    tool="stylist",
                    args={
                        "product_id": top.product_id,
                        "image_url": top.image_url,
                        "category": top.category,
                        "subcategory": top.subcategory,
                        "color": top.color,
                    },
                )
            )
        if out.total_matches > inp.offset + len(out.results):
            acts.append(
                NextAction(
                    action="more_results",
                    label=texts["more"],
                    tool=self.name,
                    args={"session_id": out.session_id, "next_page": True},
                )
            )
        if out.results:
            acts.append(
                NextAction(
                    action="feedback",
                    label=texts["feedback"],
                    tool=self.name,
                    args={"endpoint": "/m07/feedback", "decision_id": out.decision_id},
                )
            )
        return acts

    # ------------------------------------------------------------------ the search itself (M7)
    async def _search(
        self, inp: LocalShopInput, remembered_gender: str | None = None, memory_notes: list[str] | None = None
    ) -> LocalShopOutput:
        cat = self.catalogue
        parsed, from_memory = self._parsed(inp, remembered_gender)
        if from_memory and memory_notes is not None:
            texts = TEXTS[inp.language]
            memory_notes.append(texts["gender_memory"].format(gender=texts[parsed.gender]))
        notes, t = [], notes_for(inp.language)
        style_values = inp.style_vector
        if isinstance(style_values, str):  # an id, as in the architecture doc: ask M5 for the vector
            style_values = clients.style_vector_from_m5(inp.user_id, style_values)
            if style_values is None:
                notes.append(t["no_style"].format(style=inp.style_vector))
        style = self._vector(style_values, "style_vector")
        image = self._vector(inp.image_embedding, "image_embedding")

        # Visual query: a probe photo beats text; text goes through FashionCLIP's English prompt.
        visual_kind, query_vec = None, None
        if image is not None:
            visual_kind, query_vec = "image", image
        elif self.encoder is not None and parsed.prompt_en:
            visual_kind, query_vec = "text", self.encoder.encode_texts([parsed.prompt_en])[0]
        visual, bm25 = retrieve.run(cat, parsed.terms, query_vec)

        # Nothing understood (no type, colour or photo): keep only products that contain the words,
        # instead of filling the list with unrelated pieces.
        understood = parsed.subcategory or parsed.category or parsed.color or image is not None
        evidence = bm25 > 0 if (not understood and parsed.terms) else np.ones(len(cat), dtype=bool)
        # Strictest filters first, then relaxed one at a time when nothing matches: the city before the
        # colour (a colour asked for means only that colour), sold-out pieces before other colours.
        stock = inp.include_unavailable
        steps = [
            (True, True, stock),
            (False, True, stock),
            (False, True, True),
            (True, False, stock),
            (False, False, stock),
            (False, False, True),
        ]
        for use_city, use_color, with_sold_out in steps:
            mask = filter.run(cat, parsed, with_sold_out, use_city=use_city, use_color=use_color) & evidence
            if mask.any():
                break
        candidates = np.flatnonzero(mask)
        city_applied = use_city and bool(parsed.city)
        if len(candidates):
            if parsed.city and not use_city and not filter.city_mask(cat, parsed.city)[candidates].any():
                notes.append(t["other_cities"].format(city=parsed.city))
            if with_sold_out and not stock:
                notes.append(t["sold_out"].format(n=len(candidates)))
            if parsed.color and not use_color:
                notes.append(self._colour_note(parsed, city_applied, inp.language))
        if not len(candidates):
            if not evidence.any():
                asked = parsed.corrected or " ".join(t for t in (inp.query, inp.gap) if t)
                notes.append(t["nothing_for"].format(asked=asked))
            else:
                notes.append(t["no_match"])
            return LocalShopOutput(results=[], parsed=parsed, total_matches=0, note=" ".join(notes))

        match, parts = rerank.score(cat, candidates, parsed, visual, visual_kind, bm25, style, self.config)
        # Greedy MMR: its first n picks do not depend on how many are asked, so page 2 (offset=k) is
        # exactly what follows page 1, without repeats. Each page is shown by score.
        picked = rerank.mmr(cat, candidates, match, inp.offset + inp.k, self.config["mmr_lambda"])
        picked = sorted(picked[inp.offset : inp.offset + inp.k], key=lambda j: -match[j])
        results = []
        for j in picked:
            p = cat.products[candidates[j]]
            results.append(
                ShopResult(
                    shop=p["shop_name"],
                    area=self._area(p, parsed, city_applied),
                    item=p["product_name"],
                    price_tnd=p["price_tnd"],
                    match=round(float(match[j]), 3),
                    product_id=p["product_id"],
                    category=p["category"],
                    subcategory=p["subcategory"],
                    color=p.get("color") or None,
                    gender=p.get("gender") or None,
                    size=p.get("size") or None,
                    image_url=p["image_url"],
                    image_path=p.get("image_path") or None,
                    product_url=p["product_url"],
                    shop_url=p["shop_url"],
                    origin_type=p["origin_type"],
                    available=p["available"],
                    reasons=rerank.reasons(p, parsed, parts, j, visual_kind, inp.language),
                )
            )
        return LocalShopOutput(
            results=results, parsed=parsed, total_matches=len(candidates), note=" ".join(notes) or None
        )
