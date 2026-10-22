"""HTTP endpoints of M10 · Share / export cards (owner BO7). Included automatically by api/main.py.

- `POST /m10/card`: the generic endpoint of the team template (`CardRequest` → `CardResponse`).
- `/m10/cards`, `/m10/s/{code}`, `/m10/metrics`, `/m10/ambassadors`: the full API used by the other BOs.
If the extra packages of `requirements.txt` (Pillow, scikit-learn…) are not installed, the module still loads:
`/m10/card` answers with the mock and the other endpoints answer 503 with the install command.
"""

import html
import inspect
import json
from dataclasses import asdict

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from shared.base_agent import AgentError

from . import mock
from .contract import CardRequest, CardResponse, ShareCardInput, ShareCardOutput

try:  # heavy deps (Pillow, numpy, scikit-learn) live in this module's requirements.txt
    from . import service
    from .singleton import share_agent
except ImportError as _e:  # pragma: no cover - depends on the environment
    service, share_agent, _MISSING = None, None, str(_e)
else:
    _MISSING = None

api = APIRouter(prefix="/m10", tags=["M10 Share / export cards"])


# Fonts of the DressMe Figma prototype (DM Serif Display + DM Sans), also used by the BO7 demo page
FONTS = (
    "https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1"
    "&family=DM+Sans:wght@400;600;700&display=swap"
)


def _agent():
    if share_agent is None:
        raise HTTPException(
            503, f"M10 needs: pip install -r modules/m10_share_cards/requirements.txt ({_MISSING})"
        )
    return share_agent


def _impl():
    """service.py is ready, so it is served even while USE_MOCKS=true; the mock stays as a fallback."""
    return service if service is not None else mock


@api.post("/card", response_model=CardResponse)
async def card(req: CardRequest):
    out = _impl().card(req.model_dump())
    return await out if inspect.isawaitable(out) else out


class SignupBody(BaseModel):
    new_user_id: str
    channel: str | None = None  # default: channel of the latest open of the link (last touch)


@api.post("/cards", response_model=ShareCardOutput)
async def create_card(body: ShareCardInput):
    try:
        return await _agent().run(body)
    except AgentError as e:
        raise HTTPException(400, str(e)) from e


@api.get("/cards/{card_id}")
async def get_card(card_id: str):
    card = _agent().store.get_card(card_id)
    if card is None:
        raise HTTPException(404, "Card not found")
    return card


@api.get("/cards/{card_id}/image", responses={200: {"content": {"image/png": {}}}})
async def get_card_image(card_id: str):
    png = _agent().store.get_png(card_id)
    if png is None:
        raise HTTPException(404, "Image not found (or stored on S3: use image_url)")
    return Response(content=png, media_type="image/png")


@api.get("/s/{code}")
async def open_shared_link(code: str, ch: str | None = None):
    """Landing of a shared link: counts the open (+ channel) and returns what the web page / app shows."""
    try:
        card = _agent().open_link(code, ch)
    except AgentError as e:
        raise HTTPException(404, str(e)) from e
    return {
        "card_id": card["card_id"],
        "image_url": card["image_url"],
        "caption": card["caption"],
        "kind": card["kind"],
        "referral_code": code,
        "cta": "Get DressMe to recreate this look with your own clothes",
    }


@api.get("/s/{code}/page", response_class=HTMLResponse)
async def shared_link_page(code: str, request: Request, ch: str | None = None):
    """Public web page of a shared link (what a friend sees in WhatsApp / Instagram).

    Open Graph tags make the card appear as a preview in chat apps. In production dressme.tn/s/<code> serves
    it.
    """
    try:
        card = _agent().open_link(code, ch)
    except AgentError as e:
        raise HTTPException(404, str(e)) from e
    img = card["image_url"]
    img_abs = img if img.startswith("http") else str(request.base_url).rstrip("/") + img
    e = html.escape
    sharer_js = json.dumps(card["user_id"]).replace("<", "\\u003c")  # safe inside <script>
    title = {"challenge": "joined a DressMe challenge", "giveaway": "is giving a piece away"}.get(
        card["kind"], "shared a look made with DressMe"
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(card["user_id"])} {title} · DressMe</title>
<meta property="og:title" content="{e(card["user_id"])} {title}">
<meta property="og:description" content="{e(card["caption"])}">
<meta property="og:image" content="{e(img_abs)}">
<meta property="og:type" content="website"><meta name="twitter:card" content="summary_large_image">
<link href="{FONTS}" rel="stylesheet">
<style>
body{{margin:0;background:#F6F3EE;color:#211D19;
font:15px/1.5 "DM Sans",system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}}
h2{{font:400 28px/1.15 "DM Serif Display",Georgia,serif}}
main{{max-width:460px;margin:0 auto;padding:20px 16px 40px}}
.brand{{font:italic 400 28px/1 "DM Serif Display",Georgia,serif;color:#211D19}}
img{{width:100%;border-radius:24px;border:1px solid #E5DED4;margin:12px 0;background:#fff}}
.btn{{display:block;width:100%;border:0;border-radius:24px;padding:13px;font:inherit;font-weight:700;
background:#211D19;color:#fff;cursor:pointer;margin-top:10px}}
.muted{{color:#81776D;font-size:13px}}.ok{{background:#F3EADC;color:#9A744B;border-radius:18px;padding:12px}}
</style></head><body><main>
<div class="brand">DressMe</div>
<h2 style="margin:6px 0 0">{e(card["user_id"])} {title}</h2>
<img src="{e(img)}" alt="{e(card.get("alt_text") or "")}">
<p>{e(card["caption"])}</p>
<div id="cta"><button class="btn" id="join">Join DressMe and recreate this look with your own clothes</button>
<p class="muted">Free · digitise your wardrobe in minutes · outfits for the Tunisian weather</p></div>
<p class="muted">Referral code {e(code)} · via {e(_agent()._channel(ch))}</p>
</main><script>
document.getElementById("join").onclick = async () => {{
  const id = "new_" + Math.random().toString(36).slice(2, 8);
  await fetch("/m10/s/{e(code)}/signup", {{method: "POST", headers: {{"content-type": "application/json"}},
    body: JSON.stringify({{new_user_id: id}})}});
  document.getElementById("cta").innerHTML = '<p class="ok">Welcome <b>' + id + '</b>! You joined thanks to '
    + {sharer_js} + '. (Counted in the BO7 KPIs.)</p>';
}};
</script></body></html>"""


@api.post("/s/{code}/signup", status_code=204)
async def attribute_signup(code: str, body: SignupBody):
    """Called by the sign-up flow when the new user arrived through a shared link."""
    try:
        _agent().attribute_signup(code, body.new_user_id, body.channel)
    except AgentError as e:
        raise HTTPException(404, str(e)) from e


@api.get("/ambassadors")
async def ambassadors(top: int = 10):
    """Referral leaderboard: users ranked by the new users their cards brought, with tiers and points."""
    return _agent().ambassadors(top)


@api.get("/metrics")
async def share_metrics(user_id: str | None = None):
    return asdict(_agent().metrics(user_id))


# The module router: M10 API + the BO7 demo page (/bo7/demo). api/main.py only includes modules/*/router.py,
# so the BO7 own-task router is attached here; the lead can move this include to api/main.py later.
router = APIRouter()
router.include_router(api)
try:
    from bo.bo7_sharing import app as _bo7_app
    from bo.bo7_sharing import avatar as _bo7_avatar
    from bo.bo7_sharing.demo.router import router as _bo7_demo

    router.include_router(_bo7_demo)
    router.include_router(_bo7_avatar.router)  # BO9 avatar viewer + M9, for "share a 3D avatar look"
    router.include_router(_bo7_app.router)  # Flutter web build of the app (/bo7/app/)
except ImportError:  # pragma: no cover
    pass
