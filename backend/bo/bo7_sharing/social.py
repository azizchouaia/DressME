"""Owner: BO7 · the rest of the BO7 ideas, built on M10 (cards) and M15 (community), with the other teams'
modules called through bo7_sharing/integrations.py (mocks until they are built).

  idea (Task split, BO7)                      route                                   other module
  S1  light outfit feed                       GET /bo7/social/feed, POST /posts         -
  S3  outfit board export                     POST /bo7/social/board                    M2 (complete it)
  S5  wardrobe pieces tagged on shared looks  GET /bo7/social/pieces                    M1, M7 (shop the look)
  S6  recreate a friend's look from a photo   POST /bo7/social/recreate                 M1 (photo), M2 (match)
  S7  "Should I buy this?" poll for friends   POST /bo7/social/polls, /vote             M6 (verdict)
  S8  monthly wardrobe recap card             POST /bo7/social/recap                    M3 (wear stats)
  S10 give-away posts for redundant pieces    /bo7/social/giveaway(s)                   M1 (duplicates), M3
  B2  stylist sharing looks with clients      /bo7/social/stylists, /stylist/share     M14
  B3  shared looks tagged with local brands   (brand on the card + shop the look)       M7
  B4  share the style evolution timeline      POST /bo7/social/timeline                 M12
  B5  share trip outfits                      POST /bo7/social/trip                     M11
  B6  follow similar style profiles           GET /bo7/social/profiles/similar, follow  M5

Every answer carries `sources` (which module answered: the owner, or "mock").
"""

import base64
import io

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from bo.bo7_sharing import integrations as ext
from bo.bo7_sharing.social_store import store

router = APIRouter(prefix="/bo7/social", tags=["BO7 · social features"])

NAMES = {
    "usr_042": "Omar",
    "amen": "Amen",
    "yasmine": "Yasmine",
    "sarra": "Sarra",
    "ines": "Ines",
    "karim": "Karim",
}
KIND_TITLE = {
    "outfit": "Outfit",
    "board": "My look",
    "tryon": "On my avatar",
    "recap": "Monthly recap",
    "giveaway": "Give-away",
    "challenge": "Challenge",
    "poll": "Should I buy this?",
    "trip": "Trip lookbook",
    "style_timeline": "My style",
}


def name(user_id: str) -> str:
    return NAMES.get(user_id, user_id)


def _pieces(user_id: str, item_ids: list[str]) -> list[dict]:
    by = {g.item_id: g for g in ext.wardrobe(user_id)}
    missing = [i for i in item_ids if i not in by]
    if missing:
        raise HTTPException(404, f"Not in the wardrobe: {', '.join(missing)}")
    return [ext.piece(by[i]) for i in item_ids]


def _public(p: dict) -> dict:
    """A piece for the app: the photo URL, never a file path of the server."""
    img = p.get("image") or ""
    web = img.startswith(("http", "/bo7/", "/m01/", "data:"))
    return {**{k: v for k, v in p.items() if k != "image"}, "image": img if web else p.get("photo")}


def _card_item(p: dict) -> dict:
    return {k: p.get(k) for k in ("item_id", "category", "label", "image", "color_hex", "brand")}


async def _card(
    user_id: str,
    kind: str,
    items: list[dict],
    title: str,
    subtitle: str | None = None,
    stats: list[dict] | None = None,
    fmt: str = "post",
    caption: str | None = None,
    source_id: str | None = None,
) -> dict:
    """A card from M10 (the share agent)."""
    from modules.m10_share_cards.singleton import share_agent

    try:
        return await share_agent(
            {
                "user_id": user_id,
                "kind": kind,
                "format": fmt,
                "title": title,
                "subtitle": subtitle,
                "items": [_card_item(p) for p in items],
                "stats": stats or [],
                "caption": caption,
                "source_id": source_id,
            }
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"M10 could not draw the card: {e}") from e


def _feed_row(p: dict, viewer: str | None) -> dict:
    s = store()
    extra = p.get("extra") or {}
    row = {
        "post_id": p["post_id"],
        "source": "share",
        "user_id": p["user_id"],
        "user_name": name(p["user_id"]),
        "kind": p["kind"],
        "title": p.get("title") or KIND_TITLE.get(p["kind"], p["kind"]),
        "caption": p.get("caption"),
        "image_url": p.get("image_url"),
        "share_url": p.get("share_url"),
        "card_id": p.get("card_id"),
        "item_ids": p.get("item_ids", []),
        "likes": s.likes(p["post_id"]),
        "comments": len(s.comments(p["post_id"])),
        "liked": bool(viewer and s.liked(p["post_id"], viewer)),
        "created_at": p["created_at"],
        "poll": None,
        "giveaway": None,
    }
    if extra.get("poll_id"):
        row["poll"] = _poll_view(s.poll(extra["poll_id"]), viewer)
    if extra.get("giveaway_id"):
        row["giveaway"] = _giveaway_view(s.giveaway(extra["giveaway_id"]), viewer)
    return row


# =========================================================================== S1 · light outfit feed
class PublishBody(BaseModel):
    user_id: str
    card_id: str
    title: str | None = None


@router.post("/posts")
async def publish(body: PublishBody):
    """Puts a card made by M10 in the feed (any kind: outfit, board, avatar, recap, trip…)."""
    from modules.m10_share_cards.singleton import share_agent

    card = share_agent.store.get_card(body.card_id)
    if card is None:
        raise HTTPException(404, "Unknown card")
    if card.get("user_id") != body.user_id:
        raise HTTPException(403, "Only the card's owner can post it")
    p = store().add_post(body.user_id, card.get("kind", "outfit"), card, card.get("item_ids", []), body.title)
    return _feed_row(p, body.user_id)


@router.get("/feed")
async def feed(user_id: str | None = None, scope: str = "all", limit: int = 50):
    """All shared looks, newest first: BO7 posts (cards, polls, give-aways) + challenge posts of M15.
    scope=following keeps the people the user follows (and the user)."""
    from modules.m15_challenges.singleton import challenges_agent

    rows = [_feed_row(p, user_id) for p in store().posts()]
    titles = {c.challenge_id: c.title for c in challenges_agent.store.challenges.values()}
    for p in challenges_agent.feed():
        rows.append(
            {
                "post_id": p.post_id,
                "source": "challenge",
                "user_id": p.user_id,
                "user_name": name(p.user_id),
                "kind": "challenge",
                "title": f"{titles.get(p.challenge_id, p.challenge_id)} · Day {p.day}",
                "caption": p.caption,
                "image_url": p.card_image_url,
                "share_url": p.share_url,
                "card_id": None,
                "item_ids": p.item_ids,
                "likes": p.likes,
                "comments": p.comments,
                "liked": False,
                "created_at": p.created_at.isoformat(timespec="seconds"),
                "poll": None,
                "giveaway": None,
            }
        )
    if scope == "following" and user_id:
        keep = set(store().following(user_id)) | {user_id}
        rows = [r for r in rows if r["user_id"] in keep]
    rows.sort(key=lambda r: r["created_at"], reverse=True)
    return rows[:limit]


class LikeBody(BaseModel):
    user_id: str


@router.post("/posts/{post_id}/like")
async def like(post_id: str, body: LikeBody):
    if post_id.startswith("post_"):  # a challenge post: M15 keeps its likes
        from modules.m15_challenges.singleton import challenges_agent

        try:
            return {"likes": challenges_agent.like(post_id, body.user_id)}
        except Exception as e:  # noqa: BLE001
            raise HTTPException(404, str(e)) from e
    if store().post(post_id) is None:
        raise HTTPException(404, "Unknown post")
    n = store().toggle_like(post_id, body.user_id)
    return {"likes": n, "liked": store().liked(post_id, body.user_id)}


class CommentBody(BaseModel):
    user_id: str
    text: str = Field(max_length=500)


@router.get("/posts/{post_id}/comments")
async def comments(post_id: str):
    if post_id.startswith("post_"):
        from modules.m15_challenges.singleton import challenges_agent

        return [c.model_dump(mode="json") for c in challenges_agent.comments(post_id)]
    return [{**c, "user_name": name(c["user_id"])} for c in store().comments(post_id)]


@router.post("/posts/{post_id}/comments", status_code=201)
async def add_comment(post_id: str, body: CommentBody):
    """Same if/else moderation as the challenge feed (M15): no insults, links, shouting or spam."""
    from modules.m15_challenges.pipeline import moderation

    if post_id.startswith("post_"):
        from modules.m15_challenges.singleton import challenges_agent

        try:
            return challenges_agent.comment(post_id, body.user_id, body.text).model_dump(mode="json")
        except Exception as e:  # noqa: BLE001
            raise HTTPException(422, str(e)) from e
    if store().post(post_id) is None:
        raise HTTPException(404, "Unknown post")
    ok, reason = moderation.check(body.text)
    if not ok:
        raise HTTPException(422, f"Comment refused: {reason}")
    return {**store().add_comment(post_id, body.user_id, body.text.strip()), "user_name": name(body.user_id)}


# ====================================================================== S5 + B3 · pieces tagged on a look
@router.get("/pieces")
async def tagged_pieces(user_id: str, item_ids: str, shop: bool = True):
    """The pieces of a shared look (tap a tag → piece card): name, photo, colour, Tunisian brand (M1), and the
    closest products sold by Tunisian shops (M7, "shop this look")."""
    from bo.bo7_sharing import m07_local

    ids = [i for i in item_ids.split(",") if i]
    pieces = _pieces(user_id, ids)
    sources = {"pieces": "M1"}
    if shop:
        try:
            looks = await m07_local.shop_the_look(
                [
                    {
                        "item_id": p["item_id"],
                        "name": p["label"],
                        "color": p["color"],
                        "category": p["category"],
                    }
                    for p in pieces
                ]
            )
            by = {lk["item_id"]: lk.get("products", []) for lk in looks}
            for p in pieces:
                p["shop"] = by.get(p["item_id"], [])
            sources["shop"] = "M7"
        except Exception:  # noqa: BLE001 — M7 unavailable: the tags still work
            sources["shop"] = "unavailable"
    return {
        "owner": user_id,
        "owner_name": name(user_id),
        "pieces": [_public(p) for p in pieces],
        "sources": sources,
    }


# =========================================================================== S7 · "Should I buy this?" poll
class Candidate(BaseModel):
    label: str
    category: str
    color_hex: str | None = None
    image: str | None = None  # photo of the piece in the shop (data URI or URL)
    price_tnd: float | None = None
    shop: str | None = None


class PollBody(BaseModel):
    user_id: str
    candidate: Candidate
    question: str | None = None


def _poll_view(p: dict | None, viewer: str | None) -> dict | None:
    if p is None:
        return None
    total = sum(p["votes"].values())
    return {
        "poll_id": p["poll_id"],
        "user_id": p["user_id"],
        "post_id": p["post_id"],
        "question": p["question"],
        "candidate": p["candidate"],
        "verdict": p["verdict"],
        "votes": p["votes"],
        "total": total,
        "yes_share": round(p["votes"]["yes"] / total, 2) if total else None,
        "my_vote": p["voters"].get(viewer) if viewer else None,
    }


@router.post("/polls", status_code=201)
async def create_poll(body: PollBody):
    """M6 gives its verdict (Buy / Think / Skip), M10 draws the poll card, friends vote in the feed."""
    c = body.candidate.model_dump()
    verdict = ext.smartbuy_verdict(body.user_id, c)
    question = body.question or f"Should I buy this {c['label']}?"
    poll = store().add_poll(body.user_id, question, c, verdict)
    item = {
        "item_id": "candidate",
        "category": c["category"],
        "label": c["label"],
        "image": c.get("image"),
        "color_hex": c.get("color_hex"),
        "brand": c.get("shop"),
    }
    stats = [
        {"label": "AI verdict", "value": verdict["verdict"].capitalize()},
        {"label": "new outfits", "value": str(verdict.get("new_outfits", 0))},
    ]
    card = await _card(body.user_id, "poll", [item], question, "Vote with the link", stats)
    post = store().add_post(body.user_id, "poll", card, [], question, {"poll_id": poll["poll_id"]})
    store().set_poll_post(poll["poll_id"], post["post_id"])
    return {
        "poll": _poll_view(store().poll(poll["poll_id"]), body.user_id),
        "card": card,
        "post": _feed_row(post, body.user_id),
        "sources": {"verdict": verdict["source"], "card": "M10"},
    }


class VoteBody(BaseModel):
    voter_id: str
    choice: str = Field(pattern="^(yes|no)$")


@router.post("/polls/{poll_id}/vote")
async def vote(poll_id: str, body: VoteBody):
    p = store().poll(poll_id)
    if p is None:
        raise HTTPException(404, "Unknown poll")
    if body.voter_id == p["user_id"]:
        raise HTTPException(422, "Friends vote, not the author")
    store().vote(poll_id, body.voter_id, body.choice)
    return _poll_view(store().poll(poll_id), body.voter_id)


@router.get("/polls/{poll_id}")
async def get_poll(poll_id: str, user_id: str | None = None):
    p = _poll_view(store().poll(poll_id), user_id)
    if p is None:
        raise HTTPException(404, "Unknown poll")
    return p


# =========================================================================== S10 · give-away posts
@router.get("/giveaway/suggestions")
async def giveaway_suggestions(user_id: str):
    """Pieces worth giving: near-duplicates (M1) and pieces not worn this month (M3)."""
    dups = await ext.duplicates(user_id)
    stats = ext.wear_stats(user_id)
    by = {g.item_id: g for g in ext.wardrobe(user_id)}
    given = store().given_item_ids(user_id)
    out: dict[str, dict] = {}
    for group in dups["groups"]:
        ids = [i for i in group if i in by]
        for i in ids[1:]:  # keep one of each group
            out[i] = {**ext.piece(by[i]), "reason": f"you have {len(ids)} similar pieces"}
    for i, n in stats["wears"].items():
        if n == 0 and i in by and i not in out:
            out[i] = {**ext.piece(by[i]), "reason": "not worn this month"}
    items = [_public(p) for i, p in out.items() if i not in given]
    return {"items": items, "sources": {"duplicates": dups["source"], "wear_log": stats["source"]}}


class GiveawayBody(BaseModel):
    user_id: str
    item_id: str
    size: str | None = None
    condition: str = "good"
    city: str | None = None
    note: str | None = None


def _giveaway_view(g: dict | None, viewer: str | None) -> dict | None:
    if g is None:
        return None
    return {
        **{
            k: g[k]
            for k in (
                "giveaway_id",
                "user_id",
                "item_id",
                "post_id",
                "size",
                "condition",
                "city",
                "note",
                "status",
                "given_to",
            )
        },
        "requests": [{**r, "user_name": name(r["user_id"])} for r in g["requests"]],
        "requested": bool(viewer and any(r["user_id"] == viewer for r in g["requests"])),
    }


@router.post("/giveaways", status_code=201)
async def create_giveaway(body: GiveawayBody):
    [p] = _pieces(body.user_id, [body.item_id])
    g = store().add_giveaway(body.user_id, body.item_id, body.size, body.condition, body.city, body.note)
    sub = " · ".join(x for x in [f"size {body.size}" if body.size else None, body.condition, body.city] if x)
    card = await _card(body.user_id, "giveaway", [p], f"I'm giving away my {p['label']}", sub or None)
    post = store().add_post(
        body.user_id,
        "giveaway",
        card,
        [body.item_id],
        f"Give-away · {p['label']}",
        {"giveaway_id": g["giveaway_id"]},
    )
    store().update_giveaway(g["giveaway_id"], post_id=post["post_id"])
    return {
        "giveaway": _giveaway_view(store().giveaway(g["giveaway_id"]), body.user_id),
        "card": card,
        "post": _feed_row(post, body.user_id),
    }


class RequestBody(BaseModel):
    user_id: str
    message: str | None = Field(default=None, max_length=280)


@router.post("/giveaways/{giveaway_id}/request")
async def request_giveaway(giveaway_id: str, body: RequestBody):
    g = store().giveaway(giveaway_id)
    if g is None:
        raise HTTPException(404, "Unknown give-away")
    if g["status"] != "open":
        raise HTTPException(422, "This piece was already given")
    if body.user_id == g["user_id"]:
        raise HTTPException(422, "You cannot ask for your own piece")
    store().request_giveaway(giveaway_id, body.user_id, body.message)
    return _giveaway_view(store().giveaway(giveaway_id), body.user_id)


class GiveBody(BaseModel):
    user_id: str  # the owner
    to_user: str


@router.post("/giveaways/{giveaway_id}/give")
async def give(giveaway_id: str, body: GiveBody):
    g = store().giveaway(giveaway_id)
    if g is None:
        raise HTTPException(404, "Unknown give-away")
    if body.user_id != g["user_id"]:
        raise HTTPException(403, "Only the owner chooses who gets the piece")
    if body.to_user not in {r["user_id"] for r in g["requests"]}:
        raise HTTPException(422, "This friend did not ask for the piece")
    store().update_giveaway(giveaway_id, status="given", given_to=body.to_user)
    return _giveaway_view(store().giveaway(giveaway_id), body.user_id)


# =========================================================================== S3 · outfit board export
class BoardBody(BaseModel):
    user_id: str
    item_ids: list[str] = Field(min_length=1)
    title: str = "My look"
    complete: bool = True  # fill the missing slots with M2 ("complete with AI")
    publish: bool = False


@router.post("/board")
async def board(body: BoardBody):
    added, src = [], None
    if body.complete:
        fill = ext.complete_board(body.user_id, body.item_ids)
        added, src = [i for i in fill.get("added", []) if i not in body.item_ids], fill["source"]
    ids = body.item_ids + added
    pieces = _pieces(body.user_id, ids)
    card = await _card(body.user_id, "board", pieces, body.title, "Styled by me · DressMe", fmt="square")
    post = store().add_post(body.user_id, "board", card, ids, body.title) if body.publish else None
    return {
        "card": card,
        "item_ids": ids,
        "added": added,
        "post": post and _feed_row(post, body.user_id),
        "sources": {"complete": src, "card": "M10"},
    }


# =========================================================================== S8 · monthly recap card
class RecapBody(BaseModel):
    user_id: str
    month: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    publish: bool = False


@router.post("/recap")
async def recap(body: RecapBody):
    stats = ext.wear_stats(body.user_id, body.month)
    by = {g.item_id: g for g in ext.wardrobe(body.user_id)}
    worn = {i: n for i, n in stats["wears"].items() if n > 0 and i in by}
    top = sorted(worn, key=lambda i: (-worn[i], i))[:4]
    unworn = sum(1 for i in by if stats["wears"].get(i, 0) == 0)
    rotation = round(len(worn) / len(by) * 100) if by else 0
    month = stats.get("month") or body.month
    fav = by[top[0]].subcategory if top else None
    numbers = [
        {"label": "outfits logged", "value": str(stats.get("outfits", stats.get("days_logged", 0)))},
        {"label": "pieces worn", "value": f"{len(worn)}/{len(by)}"},
        {"label": "wardrobe used", "value": f"{rotation}%"},
        {"label": "never worn", "value": str(unworn)},
    ]
    pieces = [ext.piece(by[i]) for i in top]
    card = await _card(
        body.user_id,
        "recap",
        pieces,
        f"My {month} in outfits",
        f"Favourite: {fav}" if fav else None,
        numbers,
        fmt="story",
    )
    post = store().add_post(body.user_id, "recap", card, top, f"My {month}") if body.publish else None
    return {
        "card": card,
        "month": month,
        "stats": numbers,
        "top_items": top,
        "favourite": fav,
        "post": post and _feed_row(post, body.user_id),
        "sources": {"wear_log": stats["source"], "card": "M10"},
    }


# =========================================================================== B5 · trip lookbook
class TripBody(BaseModel):
    user_id: str
    destination: str = Field(min_length=1, max_length=60)
    days: int = Field(ge=1, le=14)
    publish: bool = False


@router.post("/trip")
async def trip(body: TripBody):
    plan = ext.trip_plan(body.user_id, body.destination, body.days)
    packing = plan["packing"]
    pieces = _pieces(body.user_id, packing[:6])
    title = f"{body.destination}, {body.days} days, {len(packing)} pieces"
    card = await _card(
        body.user_id,
        "trip",
        pieces,
        title,
        "Packed with DressMe",
        [{"label": "days", "value": str(body.days)}, {"label": "pieces", "value": str(len(packing))}],
    )
    post = store().add_post(body.user_id, "trip", card, packing, title) if body.publish else None
    return {
        "card": card,
        "plan": plan["days"],
        "packing": packing,
        "post": post and _feed_row(post, body.user_id),
        "sources": {"trip": plan["source"], "card": "M10"},
    }


# =========================================================================== B4 · style evolution timeline
class TimelineBody(BaseModel):
    user_id: str
    months: int = Field(default=4, ge=2, le=12)
    publish: bool = False


@router.post("/timeline")
async def timeline(body: TimelineBody):
    t = ext.style_timeline(body.user_id, body.months)
    months = t["months"]
    first, last = months[0]["style"], months[-1]["style"]
    title = f"From {first} to {last}" if first != last else f"Always {last}"
    stats = [{"label": m["month"], "value": m["style"]} for m in months[-4:]]
    by = ext.wardrobe(body.user_id)
    pieces = [ext.piece(g) for g in by if ext._colour(g)[0] == months[-1]["main_colour"]][:3]
    card = await _card(
        body.user_id,
        "style_timeline",
        pieces or [ext.piece(g) for g in by[:3]],
        title,
        f"{len(months)} months of style",
        stats,
    )
    post = store().add_post(body.user_id, "style_timeline", card, [], title) if body.publish else None
    return {
        "card": card,
        "months": months,
        "title": title,
        "post": post and _feed_row(post, body.user_id),
        "sources": {"timeline": t["source"], "card": "M10"},
    }


# =========================================================================== S6 · recreate a friend's look
class RecreateBody(BaseModel):
    user_id: str
    post_id: str | None = None  # a look from the feed
    card_id: str | None = None  # or a shared card
    photo: str | None = None  # or a photo of the look (data URI): colours of the top / bottom / shoes zones
    make_card: bool = True


def _photo_targets(photo: str) -> list[dict]:
    """Stand-in for M1's photo analysis: the main colour of the upper, lower and feet zones of the photo."""
    import numpy as np
    from PIL import Image

    from modules.m10_share_cards.pipeline import colors_ml

    try:
        raw = base64.b64decode(photo.split(",", 1)[-1])
        img = Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, "The photo cannot be read") from e
    a = np.asarray(img).astype(np.int16)
    corners = np.concatenate([a[:6, :6, :3].reshape(-1, 3), a[:6, -6:, :3].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    mask = (np.abs(a[:, :, :3] - bg).sum(axis=2) > 50) & (a[:, :, 3] > 40)
    a[:, :, 3] = np.where(mask, 255, 0)
    cut = Image.fromarray(a.astype(np.uint8), "RGBA")
    h = cut.height
    zones = [("top", 0.15, 0.50), ("bottom", 0.50, 0.88), ("shoes", 0.88, 1.0)]
    out = []
    for cat, y0, y1 in zones:
        part = cut.crop((0, int(h * y0), cut.width, int(h * y1)))
        cols = colors_ml.dominant_colors(part) if part.getbbox() else []
        if cols:
            out.append({"category": cat, "color_hex": cols[0][0], "label": f"{cat} in the photo"})
    if not out:
        raise HTTPException(422, "No garment found in the photo")
    return out


@router.post("/recreate")
async def recreate(body: RecreateBody):
    """Recreate a look with the user's own pieces: the target pieces (from a friend's post / card, or a photo)
    are matched with the closest pieces of the user's wardrobe (M2: same slot, closest colour)."""
    from modules.m10_share_cards.singleton import share_agent

    origin, owner = None, None
    if body.post_id or body.card_id:
        if body.post_id:
            p = store().post(body.post_id)
            if p is None:
                raise HTTPException(404, "Unknown post")
            owner, ids = p["user_id"], p["item_ids"]
        else:
            card = share_agent.store.get_card(body.card_id)
            if card is None:
                raise HTTPException(404, "Unknown card")
            owner, ids = card["user_id"], card.get("item_ids", [])
        by = {g.item_id: g for g in ext.wardrobe(owner)}
        targets = [
            {
                "category": ext.piece(by[i])["category"],
                "color_hex": ext.piece(by[i])["color_hex"],
                "label": ext.piece(by[i])["label"],
                "item_id": i,
            }
            for i in ids
            if i in by
        ]
        origin, photo_src = "look", None
    elif body.photo:
        targets, origin, photo_src = _photo_targets(body.photo), "photo", "mock"
    else:
        raise HTTPException(422, "Give a post_id, a card_id or a photo")
    if not targets:
        raise HTTPException(422, "This look has no piece to recreate")
    match = ext.match_pieces(body.user_id, targets)
    found = [m for m in match["items"] if m.get("item_id")]
    mine = _pieces(body.user_id, [m["item_id"] for m in found]) if found else []
    score = round(sum(m["score"] for m in found) / len(targets), 2) if targets else 0
    card = None
    if body.make_card and mine:
        who = f"{name(owner)}'s look" if owner else "a photo"
        card = await _card(
            body.user_id,
            "outfit",
            mine,
            "Recreated from my wardrobe",
            f"Inspired by {who}",
            [{"label": "match", "value": f"{round(score * 100)}%"}],
        )
    return {
        "origin": origin,
        "inspired_by": owner,
        "targets": targets,
        "pieces": [_public(p) for p in mine],
        "matches": match["items"],
        "match_score": score,
        "missing": [m["target"] for m in match["items"] if not m.get("item_id")],
        "card": card,
        "sources": {"photo": photo_src, "match": match["source"]},
    }


# =========================================================================== B2 · stylist sharing looks
@router.get("/stylists")
async def list_stylists():
    s = ext.stylists()
    return {"stylists": s["stylists"], "source": s["source"]}


@router.get("/stylists/{stylist_id}/clients")
async def list_clients(stylist_id: str):
    c = ext.clients(stylist_id)
    return {"clients": c["clients"], "source": c["source"]}


class StylistShareBody(BaseModel):
    stylist_id: str
    client_id: str
    item_ids: list[str] = Field(min_length=1)  # pieces of the client's wardrobe
    note: str | None = Field(default=None, max_length=280)


@router.post("/stylist/share", status_code=201)
async def stylist_share(body: StylistShareBody):
    """A stylist (M14) builds a look from the client's wardrobe and sends it to the client's inbox."""
    sty = {s["stylist_id"]: s for s in ext.stylists()["stylists"]}.get(body.stylist_id)
    if sty is None:
        raise HTTPException(404, "Unknown stylist")
    if body.client_id not in {c["client_id"] for c in ext.clients(body.stylist_id)["clients"]}:
        raise HTTPException(403, "Not a client of this stylist")
    pieces = _pieces(body.client_id, body.item_ids)
    card = await _card(
        body.client_id, "outfit", pieces, "A look for you", f"Styled by {sty['name']}", caption=body.note
    )
    return store().add_stylist_share(body.stylist_id, body.client_id, card, body.item_ids, body.note)


@router.get("/inbox/{client_id}")
async def inbox(client_id: str):
    sty = {s["stylist_id"]: s["name"] for s in ext.stylists()["stylists"]}
    return [
        {**r, "stylist_name": sty.get(r["stylist_id"], r["stylist_id"])} for r in store().inbox(client_id)
    ]


# =========================================================================== B6 · follow similar profiles
@router.get("/profiles/similar")
async def similar_profiles(user_id: str, top: int = 5):
    """Users whose style vector (M5) is closest to mine (cosine similarity)."""
    me = ext.style_profile(user_id)
    following = set(store().following(user_id))
    out = []
    for other in sorted(set(NAMES) - {user_id}):
        p = ext.style_profile(other)
        out.append(
            {
                "user_id": other,
                "name": name(other),
                "similarity": ext.cosine(me["vector"], p["vector"]),
                "tags": p.get("tags", []),
                "following": other in following,
            }
        )
    out.sort(key=lambda r: -r["similarity"])
    return {"profiles": out[:top], "my_tags": me.get("tags", []), "source": me["source"]}


class FollowBody(BaseModel):
    user_id: str
    target: str
    follow: bool = True


@router.post("/follow")
async def follow(body: FollowBody):
    if body.user_id == body.target:
        raise HTTPException(422, "You cannot follow yourself")
    store().follow(body.user_id, body.target, body.follow)
    return {"following": store().following(body.user_id)}


@router.get("/following")
async def following(user_id: str):
    return {"following": store().following(user_id)}


# =========================================================================== integration status
@router.get("/integrations")
async def integrations_status(user_id: str = "usr_042"):
    """Which module answers BO7 today: the owner's real module, or the BO7 mock (see INTEGRATION.md)."""
    checks = {
        "M1 wardrobe (BO3) · duplicates": lambda: None,
        "M2 recommendation (BO1/BO2) · match": lambda: ext.match_pieces(user_id, [{"category": "top"}]),
        "M3 wear log (BO1/BO2) · stats": lambda: ext.wear_stats(user_id),
        "M5 style profile (BO4) · profile": lambda: ext.style_profile(user_id),
        "M6 smart buy (BO5) · verdict": lambda: ext.smartbuy_verdict(
            user_id, {"label": "shirt", "category": "top"}
        ),
        "M11 trip planner (BO3) · plan": lambda: ext.trip_plan(user_id, "Tunis", 2),
        "M12 style evolution (BO4) · timeline": lambda: ext.style_timeline(user_id, 2),
        "M14 stylist mode (BO6) · stylists": lambda: ext.stylists(),
    }
    rows = []
    for name, call in checks.items():
        try:
            src = (await ext.duplicates(user_id))["source"] if name.startswith("M1 ") else call()["source"]
            rows.append({"module": name, "source": src, "real": src != "mock"})
        except Exception as e:  # noqa: BLE001
            rows.append({"module": name, "source": f"error: {e}", "real": False})
    return {"modules": rows, "real": sum(r["real"] for r in rows), "total": len(rows)}
