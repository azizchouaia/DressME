import numpy as np

from shared.base_agent import AgentError, BaseAgent

from . import clients
from .contract import LocalShopInput, LocalShopOutput, ParsedQuery, ShopResult
from .paths import CATALOGUE_CSV, CONFIG, INDEX_DIR, model_source
from .pipeline import filter, parse, rerank, retrieve
from .pipeline.catalogue import Catalogue
from .taxonomy import COLOR_CODES, SUBCATEGORIES, canonical_city, governorate


class LocalShopAgent(BaseAgent[LocalShopInput, LocalShopOutput]):
    name = "localshop"
    description = (
        "M7 local catalogue: find pieces sold by Tunisian shops and brands (prices in TND) that match "
        "a request (FR/EN/darija), a wardrobe gap, a photo embedding or the user's style; filters by "
        "budget, city, category and gender."
    )
    input_model = LocalShopInput
    output_model = LocalShopOutput
    is_async_job = False

    def __init__(self, config: dict | None = None, catalogue: Catalogue | None = None, encoder=None):
        super().__init__(config or CONFIG)
        # Heavy objects are created in setup() (or injected by tests), never at import time.
        self.catalogue = catalogue
        self.encoder = encoder

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

    def _parsed(self, inp: LocalShopInput) -> ParsedQuery:
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
        # The prompt follows the final slots, so calls with explicit fields only also use FashionCLIP.
        parsed.prompt_en = parse.build_prompt(parsed, " ".join(t for t in (inp.query, inp.gap) if t))
        return parsed

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
    def _colour_note(parsed: ParsedQuery, city_applied: bool) -> str:
        """The colour asked for exists nowhere (in stock or not, in any city): say it before other colours."""
        colour = COLOR_CODES[parsed.color][0].lower()
        what = SUBCATEGORIES[parsed.subcategory][1].lower() if parsed.subcategory else "articles"
        where = f" à {parsed.city}" if city_applied else ""
        return (
            f"Aucun article de couleur {colour} parmi les {what}{where} : "
            f"voici les autres {what} disponibles."
        )

    async def run(self, inp: LocalShopInput) -> LocalShopOutput:
        if self.catalogue is None:
            await self.setup()
        cat = self.catalogue
        parsed = self._parsed(inp)
        notes = []
        style_values = inp.style_vector
        if isinstance(style_values, str):  # an id, as in the architecture doc: ask M5 for the vector
            style_values = clients.style_vector_from_m5(inp.user_id, style_values)
            if style_values is None:
                notes.append(
                    f"Vecteur de style « {inp.style_vector} » pas encore disponible (M5) : "
                    "classement sans le style."
                )
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
                notes.append(
                    f"Rien trouvé à {parsed.city} : résultats d'autres villes ou de boutiques en ligne."
                )
            if with_sold_out and not stock:
                notes.append(
                    f"Aucun article en stock pour l'instant : {len(candidates)} article(s) en rupture de "
                    "stock, à vérifier auprès de la boutique."
                )
            if parsed.color and not use_color:
                notes.append(self._colour_note(parsed, city_applied))
        if not len(candidates):
            if not evidence.any():
                asked = parsed.corrected or " ".join(t for t in (inp.query, inp.gap) if t)
                notes.append(
                    f"Je n'ai trouvé aucun article correspondant à « {asked} » dans les boutiques locales."
                )
            else:
                notes.append("Aucun article ne correspond à ces critères.")
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
                    reasons=rerank.reasons(p, parsed, parts, j, visual_kind),
                )
            )
        return LocalShopOutput(
            results=results, parsed=parsed, total_matches=len(candidates), note=" ".join(notes) or None
        )
