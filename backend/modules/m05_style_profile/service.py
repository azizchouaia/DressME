"""Real implementation of M5: onboarding swipes, taste vector, style mix, card ranking.

Perception is M1's (FashionCLIP vectors + attributes, through m01_client). M5 decides, server-side. A new user
answers no question: the profile starts empty and is learnt from the swipes only.

config `ranking`:
- rocchio (default): taste = normalise(mean(liked) - 0.3 * mean(rejected) + wishes); cards ranked by
  cosine(card, taste), with a few discovery cards per batch (rocchio.py). No context, no bandit.
- bandit: per-user Linear Thompson Sampling on context x outfit features (bandit.py), kept for a taste that
  depends on the context. Every shown card is logged with its bandit features in both modes.
"""

import asyncio
import base64
import hashlib
import logging
import mimetypes
import random
import time
from pathlib import Path

import numpy as np

from . import m01_client, m02_client, m03_client, prior, rocchio, styles
from .attributes import formality as item_formality
from .attributes import warmth as item_warmth
from .bandit import LinearTS
from .config import MODULE_DIR, get_config, load_reference_looks, load_styles
from .contract import (
    Card,
    CardsResponse,
    ChooseRequest,
    Context,
    ExplainResponse,
    ExplainRule,
    FeedbackRequest,
    FeedbackResponse,
    FeedbackResult,
    InvalidAnswerError,
    PreferencesRequest,
    ProfileNotFoundError,
    ProfileResponse,
    RecomputeRequest,
    RecomputeResponse,
    StylesResponse,
)
from .features import Layout
from .repository import BanditRecord, LogRecord, LookRecord, ProfileRecord, get_store, new_log_id, now

LOOK_IMAGE = "/m05/ui/looks/{id}.svg"
UI_URL = "/m05/ui/"  # pictures served by M5 itself, from ui/ (e.g. ui/looks/photos/look_classic.jpg)
log = logging.getLogger(__name__)
_locks: dict[str, asyncio.Lock] = {}


def _lock(user_id: str) -> asyncio.Lock:
    return _locks.setdefault(user_id, asyncio.Lock())


def _unit(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def _layout(space: styles.StyleSpace) -> Layout:
    return Layout.build(space.ids, get_config().context)


def _mix_version(space: styles.StyleSpace) -> str:
    """Item mixes depend on the style list and on M1's embeddings (mock vectors differ from FashionCLIP)."""
    return f"{space.version}-{m01_client.mode()}"


def _context_vector(layout: Layout, ctx: Context) -> np.ndarray:
    occasion = get_config().context.canonical(ctx.occasion)
    return layout.context_vector(ctx.temp_c, ctx.rain, ctx.is_weekend(), occasion)


def _context_dict(ctx: Context) -> dict:
    return ctx.model_dump(mode="json") | {"weekend": ctx.is_weekend()}


# --- items: embeddings (M1) + style mixes (item_style, computed once) ----------------------------------


async def item_vectors(
    user_id: str, item_ids: list[str] | None, space: styles.StyleSpace
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """(embeddings, style mixes) of the user's items. Missing mixes are computed now and stored."""
    embs = await m01_client.embeddings(user_id, item_ids)
    store, version = get_store(), _mix_version(space)
    stored = await store.get_item_styles(list(embs), version)
    mixes = {i: np.asarray(m, dtype=float) for i, m in stored.items() if len(m) == len(space.ids)}
    missing = [i for i in embs if i not in mixes]
    if missing:
        computed = space.mix(np.array([embs[i] for i in missing]))
        new = {i: computed[n] for n, i in enumerate(missing)}
        await store.save_item_styles({i: [round(float(x), 6) for x in m] for i, m in new.items()}, version)
        mixes.update(new)
    return embs, mixes


async def compute_item_styles(user_id: str, item_ids: list[str] | None = None) -> dict[str, dict[str, float]]:
    """Style mix of items (all of the user's when item_ids is None): what an 'item created' hook calls."""
    space = await styles.get_space()
    _, mixes = await item_vectors(user_id, item_ids, space)
    return {i: space.as_dict(m) for i, m in mixes.items()}


# --- reference looks ----------------------------------------------------------------------------------

_looks_cache: dict[str, list[LookRecord]] = {}


def _local_picture(url: str | None) -> Path | None:
    """The file of a picture served by M5 itself (/m05/ui/...), None for any other URL or a missing file."""
    if not url or not url.startswith(UI_URL):
        return None
    ui = (MODULE_DIR / "ui").resolve()
    path = (ui / url[len(UI_URL) :]).resolve()
    return path if path.is_relative_to(ui) and path.is_file() else None


def _image_input(url: str) -> str:
    """M1 reads base64 or http(s) URLs, not M5's own paths: a local picture is sent as a data URL."""
    path = _local_picture(url)
    if path is None:
        return url
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _looks_version() -> str:
    """Looks file + local look photos (a replaced photo re-embeds) + style list + M1 mode (embeddings)."""
    h = hashlib.sha1((MODULE_DIR / get_config().reference_looks_file).read_bytes())
    for d in load_reference_looks():
        if d.vector_source == "image" and (path := _local_picture(d.image_url)):
            st = path.stat()
            h.update(f"{path.name}:{st.st_size}:{st.st_mtime_ns}".encode())
    return f"{h.hexdigest()[:12]}-{load_styles().version}-{m01_client.mode()}"


def _shown_picture(d) -> str:
    """The look's photo; its generated SVG placeholder when it has none (or the local file is missing)."""
    if not d.image_url or (d.image_url.startswith(UI_URL) and _local_picture(d.image_url) is None):
        return LOOK_IMAGE.format(id=d.id)
    return d.image_url


def _embed_from_photo(d) -> bool:
    """vector_source image with a usable picture; a missing local photo falls back to the description."""
    if d.vector_source != "image" or not d.image_url:
        return False
    if d.image_url.startswith(UI_URL) and _local_picture(d.image_url) is None:
        log.warning("reference look %s: %s not found, using its description", d.id, d.image_url)
        return False
    return True


async def reference_looks(reseed: bool = False) -> list[LookRecord]:
    """The reference_look table, seeded from reference_looks.json (embeddings through M1) when stale."""
    version = _looks_version()
    if version in _looks_cache and not reseed:
        return _looks_cache[version]
    store = get_store()
    looks = [] if reseed else await store.get_looks(version)
    if not looks:
        space = await styles.get_space()
        defs = load_reference_looks()
        text_defs = [d for d in defs if not _embed_from_photo(d)]
        text_vecs = await m01_client.embed_texts([d.description for d in text_defs]) if text_defs else []
        by_id = {d.id: v for d, v in zip(text_defs, text_vecs, strict=True)}
        for d in defs:
            if d.id not in by_id:
                by_id[d.id] = (await m01_client.embed_images([_image_input(d.image_url)]))[0]
        looks = [
            LookRecord(
                id=d.id,
                style_id=d.style_id,
                family=space.styles.family_of(d.style_id),
                title=d.title,
                description=d.description,
                image_url=_shown_picture(d),
                primary=d.primary,
                formality=d.formality,
                warmth=d.warmth,
                embedding=[float(x) for x in _unit(np.asarray(by_id[d.id]))],
                version=version,
            )
            for d in defs
            if d.style_id in space.ids
        ]
        await store.save_looks(looks)
    _looks_cache.clear()
    _looks_cache[version] = looks
    return looks


async def styles_info() -> StylesResponse:
    space = await styles.get_space()
    return StylesResponse(
        version=space.version,
        families={k: f.model_dump() for k, f in space.styles.families.items()},
        styles=[{"id": s.id, "family": s.family, "label": s.label or s.id} for s in space.styles.styles],
        dim=_layout(space).dim,
    )


# --- profile / bandit helpers ---------------------------------------------------------------------------


async def _get_profile(user_id: str) -> ProfileRecord:
    return await get_store().get_profile(user_id) or ProfileRecord(user_id=user_id)


async def _bandit(user_id: str, profile: ProfileRecord | None, space: styles.StyleSpace) -> BanditRecord:
    """The user's model; a new one from the prior when there is none or the style list changed (logs kept)."""
    layout = _layout(space)
    rec = await get_store().get_bandit(user_id)
    if rec is None or rec.styles_version != space.version or rec.model.dim != layout.dim:
        rec = BanditRecord(user_id, _new_model(layout, profile.answers if profile else {}), space.version)
    return rec


def _new_model(layout: Layout, answers: dict) -> LinearTS:
    cfg = get_config()
    return LinearTS(
        layout.dim, prior.build_prior(layout, answers, cfg), cfg.bandit.prior_strength, cfg.bandit.v
    )


async def _profile_response(p: ProfileRecord, space: styles.StyleSpace) -> ProfileResponse:
    mix = {s: v for s, v in p.style_mix.items() if s in space.ids}
    families = space.families(mix)
    return ProfileResponse(
        user_id=p.user_id,
        onboarded=p.onboarded,
        answers={k: v for k, v in p.answers.items() if not k.startswith("_")},
        style_mix=mix,
        families=families,
        top_families=[f for f, v in families.items() if v > 0][:2],
        top_styles=space.top(mix),
        taste_vector=p.taste_vector,
        n_feedback=await get_store().count_feedback(p.user_id),
        styles_version=space.version,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _check_styles(space: styles.StyleSpace, *groups) -> None:
    unknown = {s for g in groups for s in (g or []) if s not in space.ids}
    if unknown:
        raise InvalidAnswerError(f"unknown style ids: {sorted(unknown)}")


def _rocchio() -> bool:
    return get_config().ranking == "rocchio"


def _refresh_taste(p: ProfileRecord, space: styles.StyleSpace) -> None:
    """Rocchio: taste vector from the liked / rejected sums and the wishes; the style mix follows it."""
    vec = dict(zip(space.ids, space.vectors, strict=True))
    t = rocchio.taste(
        p.liked_sum,
        p.n_liked,
        p.rejected_sum,
        p.n_rejected,
        [vec[s] for s in p.answers.get("want_more") or [] if s in vec],
        [vec[s] for s in p.answers.get("want_less") or [] if s in vec],
    )
    p.taste_vector = None if t is None else [float(x) for x in t]
    mix = {} if t is None else space.as_dict(space.mix(t))
    p.style_mix = dict(sorted(mix.items(), key=lambda kv: -kv[1]))


async def adjust_styles(req: PreferencesRequest) -> ProfileResponse:
    """Explicit wishes ('more classic, less streetwear'). The latest wish wins over the earlier ones.
    rocchio: the wished style vectors are added to / removed from the taste (the swipes are kept).
    bandit: the prior is rebuilt and shifted (every learned update kept), the style mix moves a step."""
    cfg = get_config()
    space = await styles.get_space()
    layout = _layout(space)
    _check_styles(space, req.more, req.less)
    async with _lock(req.user_id):
        p = await get_store().get_profile(req.user_id)
        if p is None or not p.onboarded:
            raise ProfileNotFoundError(f"{req.user_id} has no profile yet: swipe the onboarding cards first")
        a = p.answers

        def merged(key: str, add: list[str], remove: list[str]) -> list[str]:
            return [s for s in dict.fromkeys([*(a.get(key) or []), *add]) if s not in remove]

        a["want_more"] = merged("want_more", req.more, req.less)
        a["want_less"] = merged("want_less", req.less, req.more)
        if _rocchio():
            _refresh_taste(p, space)
            await get_store().save_profile(p)
            return await _profile_response(p, space)
        step = cfg.chat_mix_step
        mix = {s: p.style_mix.get(s, 0.0) for s in space.ids}
        for s in req.more:
            mix[s] += step
        for s in req.less:
            mix[s] = max(0.0, mix[s] - step)
        total = sum(mix.values()) or 1.0
        p.style_mix = dict(sorted(((s, round(v / total, 4)) for s, v in mix.items()), key=lambda kv: -kv[1]))
        rec = await _bandit(req.user_id, p, space)
        rec.model.shift_prior(prior.build_prior(layout, a, cfg))  # keeps every learned update
        await get_store().save_bandit(rec)
        await get_store().save_profile(p)
        return await _profile_response(p, space)


# --- candidates -> features -------------------------------------------------------------------------------


class _Candidate:
    __slots__ = ("kind", "outfit_id", "look_id", "item_ids", "title", "images", "x", "mix", "emb", "ctx",
                 "family")

    def __init__(
        self, kind, x, mix, emb, ctx, outfit_id=None, look_id=None, item_ids=(), title=None, images=(),
        family=None,
    ):
        self.kind, self.x, self.mix, self.emb, self.ctx = kind, x, mix, emb, ctx
        self.outfit_id, self.look_id, self.item_ids = outfit_id, look_id, list(item_ids)
        self.title, self.images, self.family = title, list(images), family


def _taste(p: ProfileRecord | None) -> np.ndarray | None:
    return np.asarray(p.taste_vector) if p and p.taste_vector else None


def _outfit_candidate(layout, ctx: Context, item_ids, items_by_id, embs, mixes, taste, outfit_id=None):
    known = [i for i in item_ids if i in items_by_id and i in embs]
    if not known:
        return None
    pieces = [items_by_id[i] for i in known]
    mix = np.mean([mixes[i] for i in known], axis=0)
    emb = _unit(np.mean([embs[i] for i in known], axis=0))
    taste_sim = float(emb @ taste) if taste is not None else 0.0
    out = layout.outfit_vector(
        mix,
        float(np.mean([item_formality(i) for i in pieces])),
        float(np.mean([item_warmth(i) for i in pieces])),
        m03_client.novelty(pieces),
        taste_sim,
    )
    x = layout.features(_context_vector(layout, ctx), out)
    images = [i.image_cutout or i.image_raw for i in pieces]
    return _Candidate(
        "outfit",
        x,
        mix,
        emb,
        ctx,
        outfit_id=outfit_id or m02_client.outfit_id_for(known),
        item_ids=known,
        images=images,
    )


def _look_candidate(layout, ctx: Context, look: LookRecord, space, taste):
    emb = np.asarray(look.embedding)
    mix = space.mix(emb)
    taste_sim = float(emb @ taste) if taste is not None else 0.0
    out = layout.outfit_vector(mix, look.formality, look.warmth, get_config().m03.default_novelty, taste_sim)
    return _Candidate(
        "look",
        layout.features(_context_vector(layout, ctx), out),
        mix,
        emb,
        ctx,
        look_id=look.id,
        title=look.title,
        images=[look.image_url],
        family=look.family,
    )


async def _show(user_id: str, chosen: list[tuple[_Candidate, float, bool]], source: str, space) -> list[Card]:
    """Logs every shown card with its features (bandit_log) and builds the cards. chosen: (card, score,
    is a discovery card)."""
    logs, cards = [], []
    for rank, (c, score, explore) in enumerate(chosen):
        lg = LogRecord(
            log_id=new_log_id(),
            user_id=user_id,
            context=_context_dict(c.ctx),
            features=[float(v) for v in c.x],
            source=source,
            outfit_id=c.outfit_id,
            look_id=c.look_id,
            item_ids=c.item_ids,
            rank=rank,
            score=round(float(score), 4),
        )
        logs.append(lg)
        cards.append(
            Card(
                log_id=lg.log_id,
                kind=c.kind,
                outfit_id=c.outfit_id,
                look_id=c.look_id,
                title=c.title,
                item_ids=c.item_ids,
                images=c.images,
                context=c.ctx,
                rank=rank,
                score=round(float(score), 4),
                explore=explore,
                top_styles=space.top(space.as_dict(c.mix)),
            )
        )
    await get_store().add_logs(logs)
    return cards


def _similarities(pool: list[_Candidate], taste: np.ndarray | None) -> np.ndarray:
    """cosine(card, taste): every embedding is L2-normalised. Zeros before the first liked card."""
    if taste is None:
        return np.zeros(len(pool))
    return np.array([float(c.emb @ taste) for c in pool])


def _one_per_family(pool: list[_Candidate], n: int, rng: random.Random) -> list[int]:
    """Rocchio onboarding: one random look per style family, then random cards, in a random order."""
    idx = list(range(len(pool)))
    rng.shuffle(idx)
    picked: list[int] = []
    families_seen: set[str] = set()
    for i in idx:
        if pool[i].kind == "look" and pool[i].family not in families_seen and len(picked) < n:
            families_seen.add(pool[i].family)
            picked.append(i)
    picked += [i for i in idx if i not in picked][: n - len(picked)]
    rng.shuffle(picked)
    return picked


# --- onboarding swipes ------------------------------------------------------------------------------------


async def swipe_cards(user_id: str) -> CardsResponse:
    """The first screen of a new user, with no question before it. 10 cards: reference looks + M2 outfits in
    several situations, with at least one look per style family (rocchio: picked at random, to explore the
    user's style; bandit: in Thompson Sampling order). Creates the empty profile when there is none; the
    profile is onboarded once every card of the batch is answered (POST /feedback, source=onboarding).
    Calling it again gives a new batch, which replaces the unanswered one."""
    t0 = time.perf_counter()
    cfg = get_config()
    space = await styles.get_space()
    layout = _layout(space)
    p = await get_store().get_profile(user_id) or ProfileRecord(user_id=user_id)
    rng = random.Random()
    contexts = [Context(**c) for c in cfg.onboarding_contexts]
    taste = _taste(p)
    pool = [_look_candidate(layout, rng.choice(contexts), lk, space, taste) for lk in await reference_looks()]
    items = await m01_client.items(user_id)
    source = "reference_looks"
    if items:
        embs, mixes = await item_vectors(user_id, [i.item_id for i in items], space)
        by_id = {i.item_id: i for i in items}
        seen, sources = set(), set()
        for ctx in contexts:
            outfits, src = await m02_client.candidates(
                user_id, items, _context_dict(ctx), n=4, style_vector=p.taste_vector
            )
            sources.add(src)
            for o in outfits:
                c = _outfit_candidate(layout, ctx, o.item_ids, by_id, embs, mixes, taste, o.outfit_id)
                if c and c.outfit_id not in seen:
                    seen.add(c.outfit_id)
                    pool.append(c)
        source = "+".join(["reference_looks", *sorted(sources)])  # what really answered (m02 / m02_mock)
    n = min(cfg.bandit.onboarding_cards, len(pool))
    if _rocchio():
        scores = _similarities(pool, taste)
        picked = _one_per_family(pool, n, rng)
    else:
        rec = await _bandit(user_id, p, space)
        order, scores = rec.model.choose(np.array([c.x for c in pool]), rng=np.random.default_rng())
        picked = []
        families_seen: set[str] = set()
        for i in order:  # 1) best look of each family (the family the look was made for)
            c = pool[i]
            if c.kind == "look" and c.family not in families_seen and len(picked) < n:
                families_seen.add(c.family)
                picked.append(int(i))
        for i in order:  # 2) fill with the Thompson order
            if len(picked) >= n:
                break
            if int(i) not in picked:
                picked.append(int(i))
        picked.sort(key=lambda i: -scores[i])
    cards = await _show(user_id, [(pool[i], scores[i], False) for i in picked], "onboarding", space)
    async with _lock(user_id):
        p = await get_store().get_profile(user_id) or p
        p.answers["_onboarding_open"] = [c.log_id for c in cards]
        await get_store().save_profile(p)
    return CardsResponse(
        user_id=user_id,
        cards=cards,
        n_candidates=len(pool),
        candidates_source=source,
        styles_version=space.version,
        elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
    )


# --- daily loop -------------------------------------------------------------------------------------------


async def choose(req: ChooseRequest) -> CardsResponse:
    t0 = time.perf_counter()
    cfg = get_config()
    space = await styles.get_space()
    layout = _layout(space)
    p = await get_store().get_profile(req.user_id)
    items = await m01_client.items(req.user_id)
    by_id = {i.item_id: i for i in items}
    if req.candidates is not None:
        outfits = [
            m02_client.Outfit(item_ids=c.item_ids, outfit_id=c.outfit_id or "") for c in req.candidates
        ]
        source = "request"
    else:
        outfits, source = await m02_client.candidates(
            req.user_id, items, _context_dict(req.context), style_vector=p.taste_vector if p else None
        )
    wanted = list(dict.fromkeys(i for o in outfits for i in o.item_ids if i in by_id))
    embs, mixes = await item_vectors(req.user_id, wanted, space) if wanted else ({}, {})
    taste = _taste(p)
    pool = [
        c
        for o in outfits
        if (c := _outfit_candidate(layout, req.context, o.item_ids, by_id, embs, mixes, taste, o.outfit_id))
    ]
    k = req.k or cfg.bandit.batch_size
    if not pool:
        return CardsResponse(
            user_id=req.user_id,
            cards=[],
            n_candidates=0,
            candidates_source=source,
            styles_version=space.version,
            elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
        )
    if _rocchio():
        sims = _similarities(pool, taste)
        rng = random.Random()
        if taste is None:  # nothing liked yet: a random batch (explore) or M2's order
            n = min(k, len(pool))
            order = rng.sample(range(len(pool)), n) if req.explore else range(n)
            chosen = [(pool[i], sims[i], False) for i in order]
        elif req.explore:  # the closest to the taste + a few discovery cards
            picks = rocchio.pick(sims, k, cfg.rocchio.explore_cards, rng)
            chosen = [(pool[i], sims[i], explore) for i, explore in picks]
        else:
            chosen = [(pool[i], sims[i], False) for i in np.argsort(-sims, kind="stable")[:k]]
    else:
        rec = await _bandit(req.user_id, p, space)
        X = np.array([c.x for c in pool])
        order, scores = rec.model.choose(X, k) if req.explore else rec.model.rank(X, k)
        chosen = [(pool[i], scores[i], False) for i in order]
    cards = await _show(req.user_id, chosen, "swipe", space)
    return CardsResponse(
        user_id=req.user_id,
        cards=cards,
        n_candidates=len(pool),
        candidates_source=source,
        styles_version=space.version,
        elapsed_ms=round((time.perf_counter() - t0) * 1000, 2),
    )


async def feedback(req: FeedbackRequest) -> FeedbackResponse:
    """rocchio: liked / rejected card -> Rocchio sums -> taste vector + style mix (weight by source).
    bandit: rewards -> bandit update (weight by source) + taste vector / style mix on positive feedback."""
    cfg = get_config()
    space = await styles.get_space()
    layout = _layout(space)
    store = get_store()
    use_rocchio = _rocchio()
    async with _lock(req.user_id):
        p = await store.get_profile(req.user_id)
        if use_rocchio and p is None:  # e.g. "worn" before any swipe: the taste starts here
            p = ProfileRecord(user_id=req.user_id)
        rec = None if use_rocchio else await _bandit(req.user_id, p, space)
        items = None
        looks_by_id = None
        results: list[FeedbackResult] = []
        profile_changed = False
        for n, ev in enumerate(req.events):
            lg = await store.get_log(req.user_id, ev.log_id) if ev.log_id else None
            if ev.log_id and lg is None:
                raise InvalidAnswerError(f"events[{n}]: unknown log_id {ev.log_id}")
            if lg is None and (ev.outfit_id or ev.look_id) and not ev.item_ids:
                lg = await store.find_open_log(req.user_id, ev.outfit_id, ev.look_id)
            is_new = lg is None or (lg.reward is not None and ev.source == "worn")
            emb = None
            if lg is not None and lg.reward is not None and not is_new:
                results.append(FeedbackResult(index=n, log_id=lg.log_id, status="duplicate"))
                continue
            if is_new:  # never shown (or worn again): build its features now
                ctx = ev.context or (Context(**lg.context) if lg else Context())
                if items is None:
                    items = {i.item_id: i for i in await m01_client.items(req.user_id)}
                if looks_by_id is None:
                    looks_by_id = {lk.id: lk for lk in await reference_looks()}
                look_id = ev.look_id or (lg.look_id if lg else None)
                item_ids = ev.item_ids or (lg.item_ids if lg else [])
                if look_id and look_id in looks_by_id:
                    c = _look_candidate(layout, ctx, looks_by_id[look_id], space, _taste(p))
                else:
                    embs, mixes = await item_vectors(req.user_id, item_ids, space) if item_ids else ({}, {})
                    c = _outfit_candidate(layout, ctx, item_ids, items, embs, mixes, _taste(p), ev.outfit_id)
                if c is None:
                    raise InvalidAnswerError(f"events[{n}]: no known item / look to learn from")
                emb = c.emb
                lg = LogRecord(
                    log_id=new_log_id(),
                    user_id=req.user_id,
                    context=_context_dict(ctx),
                    features=[float(v) for v in c.x],
                    source=ev.source,
                    outfit_id=c.outfit_id,
                    look_id=c.look_id,
                    item_ids=c.item_ids,
                )
            x = np.asarray(lg.features)
            reward, weight = cfg.rewards[ev.reaction], cfg.source_weights[ev.source]
            lg.reward, lg.reaction, lg.source, lg.rewarded_at = reward, ev.reaction, ev.source, now()
            if is_new:
                await store.add_logs([lg])
            else:
                await store.set_reward(lg)
            if use_rocchio:
                profile_changed |= await _learn_rocchio(p, lg, reward, weight, space, emb)
            elif x.shape != (layout.dim,):  # shown with an older style list: logged, not learned
                results.append(FeedbackResult(index=n, log_id=lg.log_id, status="skipped", reward=reward))
                continue
            else:
                rec.model.update(x, reward, weight)
            results.append(
                FeedbackResult(index=n, log_id=lg.log_id, status="applied", reward=reward, weight=weight)
            )
            if ev.source == "worn":
                await m03_client.record_worn(req.user_id, lg.item_ids)
            if p is not None and ev.source == "onboarding":
                profile_changed |= _close_onboarding_card(p, lg.log_id)
            if not use_rocchio and reward >= cfg.positive_reward and p is not None:
                profile_changed |= await _learn_taste(p, lg, x, layout, space)
        if rec is not None:
            await store.save_bandit(rec)
        if profile_changed:
            await store.save_profile(p)
        applied = sum(r.status == "applied" for r in results)
        return FeedbackResponse(
            user_id=req.user_id,
            applied=applied,
            results=results,
            n_feedback=await store.count_feedback(req.user_id),
        )


def _close_onboarding_card(p: ProfileRecord, log_id: str) -> bool:
    """An onboarding card was answered: the profile is onboarded once the whole batch is."""
    still_open = p.answers.get("_onboarding_open") or []
    if log_id not in still_open:
        return False
    still_open.remove(log_id)
    p.answers["_onboarding_open"] = still_open
    p.onboarded = p.onboarded or not still_open
    return True


async def _card_embedding(user_id: str, lg: LogRecord) -> np.ndarray | None:
    """FashionCLIP vector of a logged card: the reference look's, or the mean of the outfit's pieces."""
    if lg.look_id:
        looks_by_id = {lk.id: lk for lk in await reference_looks()}
        return np.asarray(looks_by_id[lg.look_id].embedding) if lg.look_id in looks_by_id else None
    embs = await m01_client.embeddings(user_id, lg.item_ids)
    return _unit(np.mean(list(embs.values()), axis=0)) if embs else None


async def _learn_rocchio(
    p: ProfileRecord, lg: LogRecord, reward: float, weight: float, space, emb: np.ndarray | None = None
) -> bool:
    """A liked card goes into the liked sum, a rejected one into the rejected sum ("ignored" into none);
    then taste = normalise(mean(liked) - reject_weight * mean(rejected) + wishes)."""
    cfg = get_config()
    liked = reward >= cfg.positive_reward
    if not liked and reward > cfg.rocchio.negative_reward:
        return False
    emb = emb if emb is not None else await _card_embedding(p.user_id, lg)
    if emb is None:
        return False
    if liked:
        p.liked_sum, p.n_liked = rocchio.accumulate(p.liked_sum, p.n_liked, emb, weight)
    else:
        p.rejected_sum, p.n_rejected = rocchio.accumulate(p.rejected_sum, p.n_rejected, emb, weight)
    _refresh_taste(p, space)
    return True


async def _learn_taste(p: ProfileRecord, lg: LogRecord, x: np.ndarray, layout: Layout, space) -> bool:
    """bandit ranking. taste = normalise((1 - lr) * taste + lr * outfit embedding); same average on the
    style mix. lr = max(taste_lr, 1 / n likes): the exact mean of the first liked cards, then a moving
    average that follows the user's taste as it changes."""
    n = int(p.answers.get("_n_liked", 0)) + 1
    p.answers["_n_liked"] = n
    lr = max(get_config().taste_lr, 1.0 / n)
    emb = await _card_embedding(p.user_id, lg)
    if emb is not None:
        old = np.asarray(p.taste_vector) if p.taste_vector else None
        p.taste_vector = [float(v) for v in (emb if old is None else _unit((1 - lr) * old + lr * emb))]
    mix = x[1 : 1 + layout.S]
    p.style_mix = {
        s: round((1 - lr) * p.style_mix.get(s, 0.0) + lr * float(mix[k]), 4) for k, s in enumerate(space.ids)
    }
    return True


# --- profile / explain / styles ----------------------------------------------------------------------------


async def profile(user_id: str) -> ProfileResponse:
    p = await get_store().get_profile(user_id)
    if p is None:
        raise ProfileNotFoundError(user_id)
    return await _profile_response(p, await styles.get_space())


async def delete_profile(user_id: str) -> dict:
    """Removes the profile, the bandit and its logs (privacy / demo reset). M1 items are untouched."""
    if not await get_store().delete_user(user_id):
        raise ProfileNotFoundError(user_id)
    return {"user_id": user_id, "deleted": True}


async def explain(user_id: str, log_id: str | None = None, k: int = 5) -> ExplainResponse:
    space = await styles.get_space()
    layout = _layout(space)
    store = get_store()
    p = await store.get_profile(user_id)
    if p is None:
        raise ProfileNotFoundError(user_id)
    if _rocchio():
        return await _explain_rocchio(p, log_id, k, space, layout)
    model = (await _bandit(user_id, p, space)).model
    theta, std = model.mean, model.std()
    labels = space.labels()

    def rule(i: int, w: float) -> ExplainRule:
        key, label = layout.describe(i, w, labels)
        return ExplainRule(
            feature=key, label=label, weight=round(float(w), 4), uncertainty=round(float(std[i]), 4)
        )

    idx = [i for i in np.argsort(-theta) if i != 0]
    positive = [rule(i, theta[i]) for i in idx if theta[i] > 1e-6][:k]
    negative = [rule(i, theta[i]) for i in reversed(idx) if theta[i] < -1e-6][:k]
    card = None
    if log_id:
        lg = await store.get_log(user_id, log_id)
        if lg is None:
            raise ProfileNotFoundError(f"log {log_id}")
        x = np.asarray(lg.features)
        if x.shape == theta.shape:
            contrib = x * theta
            top = [i for i in np.argsort(-np.abs(contrib)) if i != 0 and abs(contrib[i]) > 1e-6][:k]
            card = [rule(i, contrib[i]) for i in top]
    return ExplainResponse(
        user_id=user_id,
        n_feedback=await store.count_feedback(user_id),
        positive=positive,
        negative=negative,
        card=card,
    )


async def _explain_rocchio(
    p: ProfileRecord, log_id: str | None, k: int, space, layout: Layout
) -> ExplainResponse:
    """positive: the styles of the taste. negative: the styles rejected more than liked. card: its cosine to
    the taste, then the styles it shares with the taste (card share x taste share)."""
    store = get_store()
    labels = space.labels()

    def rule(s: str, w: float) -> ExplainRule:
        key, label = layout.describe(1 + space.ids.index(s), w, labels)
        return ExplainRule(feature=key, label=label, weight=round(float(w), 4))

    mix = {s: p.style_mix.get(s, 0.0) for s in space.ids}
    positive = [rule(s, v) for s, v in sorted(mix.items(), key=lambda kv: -kv[1]) if v > 1e-3][:k]
    negative = []
    if p.n_rejected > 0:
        rejected = space.as_dict(space.mix(_unit(np.asarray(p.rejected_sum))))
        gap = {s: rejected[s] - mix[s] for s in space.ids}
        negative = [rule(s, -g) for s, g in sorted(gap.items(), key=lambda kv: -kv[1]) if g > 1e-3][:k]
    card = None
    if log_id:
        lg = await store.get_log(p.user_id, log_id)
        if lg is None:
            raise ProfileNotFoundError(f"log {log_id}")
        emb = await _card_embedding(p.user_id, lg)
        if emb is not None and p.taste_vector:
            sim = float(emb @ np.asarray(p.taste_vector))
            label = layout.describe(layout.taste_index, sim, labels)[1]
            card = [ExplainRule(feature="taste_sim", label=label, weight=round(sim, 4))]
            card_mix = space.as_dict(space.mix(emb))
            shared = sorted(((s, card_mix[s] * mix[s]) for s in space.ids), key=lambda kv: -kv[1])
            card += [rule(s, w) for s, w in shared[: k - 1] if w > 1e-4]
    return ExplainResponse(
        user_id=p.user_id,
        n_feedback=await store.count_feedback(p.user_id),
        positive=positive,
        negative=negative,
        card=card,
    )


async def recompute(req: RecomputeRequest) -> RecomputeResponse:
    """After a style-list change: new style vectors, stale item mixes dropped (recomputed lazily, or now for
    `user_id`). Bandits of the old list restart from their prior on their next use; logs are kept."""
    space = await styles.get_space(reload=True)
    dropped = await get_store().drop_stale_item_styles(_mix_version(space))
    recomputed = len(await compute_item_styles(req.user_id)) if req.user_id else 0
    return RecomputeResponse(
        styles_version=space.version,
        n_styles=len(space.ids),
        dim=_layout(space).dim,
        dropped=dropped,
        recomputed=recomputed,
    )


# --- week-1 envelope (POST /m05/profile) ------------------------------------------------------------------


async def profile_envelope(req: dict) -> dict:
    user_id = req.get("user_id") or ""
    p = await get_store().get_profile(user_id) if user_id else None
    if p is None:
        return {"result": {"user_id": user_id, "onboarded": False}, "mocked": False}
    out = (await _profile_response(p, await styles.get_space())).model_dump(
        mode="json", exclude={"taste_vector"}
    )
    return {"result": out, "mocked": False}
