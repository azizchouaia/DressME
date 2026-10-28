"""Real teammates' modules, with the mock as a safety net.

config.yaml -> real: [m1, m7]  : those modules are called for real; the others stay mocked.
Every call falls back to the mock if the real module fails or does not know the user,
so the demo never breaks. `sources` tells which one answered (shown in the output, for honesty).

Calls are in-process (same FastAPI backend, monorepo). Set DRESSME_API_URL to call a running API over HTTP.
"""

import asyncio
import concurrent.futures
import logging
import os

from .. import synthetic as syn
from .mocks import MockClients

log = logging.getLogger("m06.clients")

# M1 subcategory (modules/m01_wardrobe/config.yaml) -> Smart Buy type. Same family = same rules.
M1_TYPES = {"t-shirt": "t-shirt", "tank top": "t-shirt", "polo shirt": "shirt", "shirt": "shirt",
            "linen shirt": "shirt", "blouse": "blouse", "sweater": "sweater", "sweatshirt": "sweater",
            "hoodie": "sweater", "jeans": "jeans", "chinos": "chinos", "trousers": "trousers", "shorts": "chinos",
            "skirt": "skirt", "dress": "dress", "summer dress": "dress", "evening dress": "dress",
            "jacket": "jacket", "leather jacket": "jacket", "denim jacket": "jacket", "blazer": "blazer",
            "coat": "coat", "sneakers": "sneakers", "loafers": "loafers", "dress shoes": "loafers",
            "boots": "boots", "sandals": "sandals", "heels": "sandals", "jebba": "jebba", "kachabia": "coat",
            "blouza": "dress", "sefsari": "jebba"}
COLOURS = {"light_blue": "blue", "khaki": "olive", "yellow": "mustard", "cream": "beige", "ivory": "white",
           "tan": "camel", "maroon": "burgundy", "charcoal": "grey"}

_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _sync(coro_or_value):
    """Their functions are async, ours are sync: run the coroutine in a worker thread."""
    if asyncio.iscoroutine(coro_or_value):
        return _pool.submit(asyncio.run, coro_or_value).result(timeout=60)
    return coro_or_value


def _dump(x):
    return x.model_dump(mode="json") if hasattr(x, "model_dump") else x


def _colour(colors: list) -> str:
    name = (colors[0]["name"] if colors else "") or ""
    name = COLOURS.get(name.lower(), name.lower())
    return name if name in syn.COLOURS else "black"


def _from_m1(g: dict) -> dict:
    """M1 WardrobeItem -> Smart Buy item. Raises KeyError for types Smart Buy does not judge (accessories)."""
    sub = M1_TYPES[(g.get("subcategory") or "").lower()]
    col = _colour(g.get("colors") or [])
    return {"id": g["item_id"], "category": syn.TYPES[sub][0], "subcategory": sub, "colour": col,
            "label": syn.label(f"{col} {sub}"), "price_tnd": g.get("price_tnd"), "brand": g.get("brand"),
            "size": g.get("size"), "wear_count": g.get("wear_count", 0), "last_worn": g.get("last_worn"),
            "image": g.get("image_cutout") or g.get("image_raw"), "m1_subcategory": g.get("subcategory")}


class HybridClients:
    def __init__(self, real: list[str], dataset: str = "synthetic"):
        self.mock = MockClients(dataset)
        self.real = {r.lower() for r in real}
        self.url = os.environ.get("DRESSME_API_URL")
        self.sources: dict[str, str] = {}
        self._probe: dict[str, str] = {}  # embedding id -> image, M1 /similar works from the image

    def __getattr__(self, name):  # anything else (mock stores used by the UI and tests) -> the mock
        return getattr(self.__dict__["mock"], name)

    # demo / test users live in the mock; a signed-in user's wardrobe is their real M1 wardrobe
    def _is_real_user(self, user_id: str) -> bool:
        """A signed-in user (not a synthetic one), or a synthetic id that has pieces in the real M1 (demo account)."""
        if "m1" not in self.real:
            return False
        from modules.m01_wardrobe.config import use_mocks
        from shared.config import settings

        if use_mocks(settings.use_mocks):
            return False  # M1 on its mock: no real wardrobe to read
        if user_id not in self.mock.wardrobes:
            return True
        try:
            from modules.m01_wardrobe.contract import ItemsRequest

            return bool(self._m1("items", ItemsRequest(user_id=user_id))["items"])
        except Exception:  # noqa: BLE001 - M1 down: the synthetic wardrobe
            return False

    @property
    def wardrobes(self):
        out = dict(self.mock.wardrobes)
        for uid, items in self.__dict__.setdefault("_real_cache", {}).items():
            out[uid] = {"items": items}
        return out

    @property
    def candidates(self):
        return self.mock.candidates

    def _try(self, module: str, name: str, real_fn, mock_fn):
        if module in self.real:
            try:
                out = real_fn()
                self.sources[name] = module
                return out
            except Exception as e:  # noqa: BLE001 - any failure -> mock, logged
                log.info("%s.%s -> mock (%s)", module, name, e)
        self.sources[name] = "mock"
        return mock_fn()

    # ---------- transport
    def _m1(self, fn: str, req):
        if self.url:
            import httpx
            path = {"classify": "/m01/classify", "similar": "/m01/similar", "items": "/m01/items"}[fn]
            r = httpx.post(self.url + path, json=_dump(req), timeout=60)
            r.raise_for_status()
            return r.json()
        from modules.m01_wardrobe import router as m1
        return _dump(_sync(getattr(m1._impl(), fn)(req)))

    def _m7(self, body: dict) -> dict:
        if self.url:
            import httpx
            r = httpx.post(self.url + "/m07/search", json=body, timeout=60)
            r.raise_for_status()
            return r.json()
        from modules.m07_local_catalogue import service as m7
        return _dump(_sync(m7.search(body, channel="smartbuy")))

    # ---------- M1 · wardrobe digitiser (BO3)
    def _is_photo(self, image: str) -> bool:
        return image.startswith(("data:", "http://", "https://")) or len(image) > 500

    def classify(self, image: str) -> dict:
        def real():
            if not self._is_photo(image):
                raise ValueError("demo id, not a photo")
            from modules.m01_wardrobe.contract import ClassifyRequest
            r = self._m1("classify", ClassifyRequest(user_id="smartbuy", image=image, mode="smartbuy_probe"))
            c = _from_m1(r["garment"])
            c["embedding"] = r["embedding"]
            c["confidence"] = r["garment"].get("confidence")
            self._probe[str(id(c["embedding"]))] = image
            return c
        out = self._try("m1", "classify", real, lambda: self.mock.classify(image))
        self.__dict__["_last_cand"] = out
        return out

    def _m1_items(self, user_id: str) -> list[dict]:
        from modules.m01_wardrobe.contract import ItemsRequest
        out = []
        for g in self._m1("items", ItemsRequest(user_id=user_id))["items"]:
            try:
                out.append(_from_m1(g))
            except KeyError:
                continue  # accessories: not judged by Smart Buy
        if not out:
            raise LookupError(f"user {user_id} has no wardrobe in M1")
        return out

    def _wears_per_year(self, user_id: str) -> dict[str, float]:
        """Real wear counts from the wear log (M3): wears in the last 90 days x 4 = per year."""
        try:
            from modules.m03_wear_log import router as m3

            r = m3._impl().stats({"user_id": user_id, "payload": {}})
            r = _sync(r)
            return {s["item_id"]: 4 * (s.get("wears_90d") or 0) for s in (_dump(r).get("result") or {}).get("items", [])}
        except Exception as e:  # noqa: BLE001 - no wear log yet
            log.info("M3 wear log unavailable (%s)", e)
            return {}

    def _real_items(self, user_id: str) -> list[dict]:
        """The signed-in user's real wardrobe (M1) with real wear counts (M3). Empty wardrobe = []."""
        from modules.m01_wardrobe.contract import ItemsRequest

        wears = self._wears_per_year(user_id)
        out = []
        for g in self._m1("items", ItemsRequest(user_id=user_id))["items"]:
            try:
                it = _from_m1(g)
            except KeyError:
                continue  # accessories: not judged by Smart Buy
            it["wear_count"] = wears.get(it["id"], it.get("wear_count") or 0)
            it["image"] = g.get("image_cutout") or g.get("image_raw")
            out.append(it)
        self.__dict__.setdefault("_real_cache", {})[user_id] = out
        return out

    def _m1_wardrobe(self, user_id):
        if self._is_real_user(user_id):
            return self._real_items(user_id)
        # demo users: M1's wardrobe only when the photo was read by M1 (same ids, same vectors)
        if self.sources.get("classify") != "m1":
            raise LookupError("demo candidate: the wardrobe stays in the mock")
        return self._m1_items(user_id)

    def items(self, user_id):
        if self._is_real_user(user_id):
            self.sources["items"] = "m1"
            return self._real_items(user_id)  # the real wardrobe, even when it is empty
        return self._try("m1", "items", lambda: self._m1_wardrobe(user_id), lambda: self.mock.items(user_id))

    def count_type(self, user_id, subcategory):
        return sum(i["subcategory"] == subcategory for i in self.items(user_id))

    def _similar_by_type(self, user_id, k):
        """No photo (type + colour picked by hand): same type and colour = very close, same type = close."""
        cand = self.__dict__.get("_last_cand") or {}
        out = []
        for it in self._real_items(user_id):
            s = 0.0
            if it["subcategory"] == cand.get("subcategory"):
                s = 0.9 if it["colour"] == cand.get("colour") else 0.6
            elif it["category"] == cand.get("category"):
                s = 0.35 if it["colour"] == cand.get("colour") else 0.2
            out.append({**{f: it[f] for f in ("label", "category", "subcategory", "colour")}, "item_id": it["id"], "similarity": s})
        return sorted(out, key=lambda n: -n["similarity"])[:k]

    def similar(self, user_id, embedding, k):
        if self._is_real_user(user_id) and not self._probe.get(str(id(embedding))):
            self.sources["similar"] = "m1"
            return self._similar_by_type(user_id, k)

        def real():
            image = self._probe.get(str(id(embedding)))
            if not image:
                raise ValueError("no probe photo for M1 /similar")
            from modules.m01_wardrobe.contract import SimilarRequest
            by_id = {i["id"]: i for i in self._m1_wardrobe(user_id)}
            r = self._m1("similar", SimilarRequest(user_id=user_id, image=image, k=k, threshold=0.0))
            return [{**{f: by_id[n["item_id"]][f] for f in ("label", "category", "subcategory", "colour")},
                     "item_id": n["item_id"], "similarity": round(max(0.0, n["similarity"]), 3)}
                    for n in r["neighbours"] if n["item_id"] in by_id]
        return self._try("m1", "similar", real, lambda: self.mock.similar(user_id, embedding, k))

    # ---------- M2 · outfits (BO1/BO2)
    def recommend_with(self, user_id, candidate):
        if self._is_real_user(user_id):
            return self._try("m2", "recommend_with", lambda: self._recommend_real(user_id, candidate), lambda: [])

        def real():
            # M2 scores 1024-d vectors (image + text FashionCLIP). M1 sends 512-d today -> not compatible yet.
            if len(candidate.get("embedding") or []) != 1024:
                raise ValueError("M2 needs 1024-d item vectors (M1 sends 512-d): waiting for M1/M2 agreement")
            from modules.m02_recommendation import router as m2
            items = [{"item_id": i["id"], "user_id": user_id, "image_raw": i.get("image") or "",
                      "category": i["category"], "subcategory": i["subcategory"],
                      "colors": [{"name": i["colour"], "hex": "#000000", "share": 1}], "embedding": i["embedding"]}
                     for i in self.items(user_id) + [{**candidate, "id": candidate.get("id", "candidate")}]]
            r = m2._impl().complete({"user_id": user_id, "payload": {
                "items": items, "pinned_item_ids": [candidate.get("id", "candidate")], "options": {"n": 10}}})
            return [{"items": [s for s in o["item_ids"] if s != candidate.get("id")]} for o in r["result"]["outfits"]]
        return self._try("m2", "recommend_with", real, lambda: self.mock.recommend_with(user_id, candidate))

    def _recommend_real(self, user_id, candidate):
        """The user's M1 pieces (1024-d: M1 image + M2 text) + the candidate -> M2 outfits with it."""
        from shared.user_wardrobe import _text_vec, description, m1_garments

        mine = m1_garments(user_id)
        if not mine:
            raise LookupError("the user's wardrobe is not usable by M2 yet")
        desc = description({"colors": [{"name": candidate["colour"]}], "subcategory": candidate["subcategory"]})
        text = list(_text_vec(desc))
        img = candidate.get("embedding") or []
        vec = (list(img) if len(img) == 512 else text) + text  # no photo: the text vector stands for the image
        cid = "smartbuy_candidate"
        items = mine + [{"item_id": cid, "user_id": user_id, "image_raw": "", "category": candidate["category"],
                         "subcategory": candidate["subcategory"], "colors": [{"name": candidate["colour"], "hex": "#000000", "share": 1}],
                         "status": "available", "embedding": vec}]
        from modules.m02_recommendation import router as m2

        r = m2._impl().complete({"user_id": user_id, "payload": {"items": items, "pinned_item_ids": [cid], "options": {"n": 10}}})
        r = _dump(r)
        if r.get("mocked"):
            raise RuntimeError("M2 runs on its mock (M02_USE_MOCK=false + model weights for real outfits)")
        return [{"items": [s for s in o["item_ids"] if s != cid]} for o in (r.get("result") or r)["outfits"]]

    # ---------- M5 · style profile (BO4): no branch yet -> mock
    def gaps(self, user_id):  # M5 (BO3, Bali) not built yet: real users get none, never fake gaps
        return [] if self._is_real_user(user_id) else self.mock.gaps(user_id)

    def goals(self, user_id):  # M12 (BO4, Bali) not built yet: empty for real users
        return {"templates": [], "budget": {}} if self._is_real_user(user_id) else self.mock.goals(user_id)

    def set_goals(self, user_id, goals):
        return self.mock.set_goals(user_id, goals)

    # ---------- M7 · local catalogue (BO6)
    def catalogue_search(self, category, colour, max_price, embedding=None, k=3):
        """Local pieces that look like the probe photo (embedding) or match type + colour, within budget."""
        def real():
            body = {"k": k, "max_price_tnd": max_price}
            if embedding is not None and len(embedding) == 512 and self.sources.get("classify") == "m1":
                body["image_embedding"] = list(embedding)  # real FashionCLIP photo vector -> same look
            else:
                body.update(subcategory={"t-shirt": "tshirt", "jebba": "traditional"}.get(category, category),
                            color=colour)
            r = self._m7(body)
            return [{"shop": x["shop"], "city": x.get("area"), "item": x["item"], "price_tnd": x.get("price_tnd"),
                     "url": x["product_url"], "image_url": x["image_url"], "product_id": x["product_id"],
                     "match": x["match"], "search_id": r.get("search_id"), "rank": n + 1, "source": "m7"}
                    for n, x in enumerate(r["results"])]
        return self._try("m7", "catalogue_search", real, lambda: self.mock.catalogue_search(category, colour, max_price))

    # ---------- M8 · LLM layer (BO8): its /explain speaks about outfits, not verdicts -> mock
    def explain(self, facts):
        return self.mock.explain(facts)
