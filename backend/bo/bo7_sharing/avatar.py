"""Owner: BO7 · "Share a 3D avatar look" (BO7 selected idea 4): the avatar from BO9 (M9) on a share card.

BO9 (feat/bo9-avatar-3d) ships the avatar as a Three.js viewer (avatar_studio/web/viewer) + a Flutter shell.
Rule 4 · nothing in avatar_studio/ is changed. This file only:
  - serves that viewer on the API's address (/bo7/avatar/viewer/), so the BO7 Flutter screen can embed it and
    take a picture of it (same origin, no CORS). A small script is added to the page *as it is served*:
      · the WebGL canvas keeps its last frame (preserveDrawingBuffer), so it can be read;
      · the files the viewer asks for at the site root (/presets/*.glb, /smplx_body.glb, /users/*) are read
        from avatar_studio/web/, where BO9 puts them;
      · BO9's garments (/garments/shirt.glb, shorts.glb, vest.glb, worn by the body since viewer-bo9) are
        served in the colours of the pieces picked for the card: ?top=, ?bottom=, ?outer= on the viewer URL
        (shirt = top, shorts = bottom). Their folds are kept, only the colour changes. The vest is left out
        while BO9's vest mesh is half built;
      · a message {type: "bo7-snapshot"} from the parent page answers {type: "bo7-snapshot", png: dataURL}.
  - asks M9 (`/m09/render`, BO9's module) for a rendered avatar image, through M9's public function.
    M9 is still a mock: it returns no image, so the Flutter screen uses the viewer picture or a picked image.
The picture goes to M10 as `avatar_image` of a "tryon" card: avatar on the left, the pieces (M1) next to it.
"""

import json
import re
import struct
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response

ROOT = Path(__file__).resolve().parents[3] / "avatar_studio" / "web"  # BO9's web folder (repo root)
VIEWER = ROOT / "viewer"
router = APIRouter(prefix="/bo7/avatar", tags=["BO7 avatar share (M9 + M10)"])
# Windows maps .mjs to text/plain (registry), and the browser then refuses to run the module: set the types.
JS = "text/javascript"
TYPES = {".mjs": JS, ".js": JS, ".glb": "model/gltf-binary", ".html": "text/html"}
GARMENT_SLOT = {"shirt": "top", "shorts": "bottom", "vest": "outer"}

PATCH = """<script>
/* BO7: added when served by /bo7/avatar/viewer/ (BO9's file is unchanged) */
(() => {
  const get = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (type, opts) {
    if (type === 'webgl' || type === 'webgl2') {
      opts = Object.assign({}, opts, { preserveDrawingBuffer: true });
    }
    return get.call(this, type, opts);
  };
  const fetch0 = window.fetch.bind(window);
  const look = new URLSearchParams(location.search);
  const fix = (u) => {
    const url = new URL(u, location.href);
    if (url.origin !== location.origin) return null;
    const garment = url.pathname.match(/^\\/garments\\/(shirt|shorts|vest)\\.glb$/);
    if (garment) {
      const q = new URLSearchParams();
      for (const k of ['user', 'top', 'bottom', 'topc', 'bottomc']) {
        if (look.get(k)) q.set(k, look.get(k));
      }
      return '/bo7/avatar/garment/' + garment[1] + '.glb?' + q.toString();
    }
    const bo9 = /^\\/(presets\\/|users\\/|garments\\/|smplx_body\\.glb|smplx_thin\\.glb)/;
    return bo9.test(url.pathname) ? '/bo7/avatar/files' + url.pathname + url.search : null;
  };
  window.fetch = (input, init) => {
    const to = fix(typeof input === 'string' ? input : input.url);
    if (to) input = typeof input === 'string' ? to : new Request(to, input);
    return fetch0(input, init);
  };
  window.addEventListener('message', (event) => {
    let data = event.data;
    try { data = typeof data === 'string' ? JSON.parse(data) : data; } catch (e) { return; }
    if (!data || data.type !== 'bo7-snapshot') return;
    // BO9's "stand" pose (arms down) for the card, instead of the T-pose: same body, it only moves the arms
    const stand = document.querySelector('[data-preset="stand"]');
    if (stand && !stand.classList.contains('active')) stand.click();
    const source = event.source;
    setTimeout(() => requestAnimationFrame(() => {  // the cloth of the garments settles after a pose change
      const canvas = document.getElementById('c');
      let png = '';
      try { png = canvas ? canvas.toDataURL('image/png') : ''; } catch (e) { png = ''; }
      source.postMessage(JSON.stringify({ type: 'bo7-snapshot', png }), '*');
    }), 900);
  });
})();
</script>
"""


def viewer_html() -> str:
    page = VIEWER / "index.html"
    if not page.exists():
        raise HTTPException(404, "BO9 avatar viewer not found (avatar_studio/web/viewer, feat/bo9-avatar-3d)")
    html = page.read_text(encoding="utf-8")
    # new address for BO9's module, so a browser that cached it with the wrong type (Windows) loads it again
    html = re.sub(r"(scene\.mjs\?v=[\w.]+)", r"\1&bo7=2", html)
    return html.replace("<head>", "<head>\n" + PATCH, 1) if "<head>" in html else PATCH + html


@router.get("/viewer/", response_class=HTMLResponse, include_in_schema=False)
async def viewer() -> str:
    return viewer_html()


def _inside(base: Path, rel: str) -> Path:
    p = (base / rel).resolve()
    if base.resolve() not in p.parents or not p.is_file():
        raise HTTPException(404, "not found")
    return p


def _file(p: Path) -> FileResponse:
    return FileResponse(p, media_type=TYPES.get(p.suffix.lower()), headers={"Cache-Control": "no-cache"})


# BO9's cloth step still uses the three.js API renamed in r151 (boneTransform, `skinning` option): it
# throws, and once renamed it skins the garments twice (CPU then GPU), so the sleeves fly off. In the copy
# that is served the cloth step is off: the garments follow the body by their skin. BO9's file is unchanged.
SCENE_FIXES = [
    ("function stepCloth(dt) {\n", "function stepCloth(dt) {\n  return 0 // BO7: cloth off\n"),
    ("          skinning: true,\n", ""),
]


@router.get("/viewer/{name:path}", include_in_schema=False)
async def viewer_file(name: str):
    p = _inside(VIEWER, name)
    if p.name == "scene.mjs":
        code = p.read_text(encoding="utf-8")
        for old, new in SCENE_FIXES:
            code = code.replace(old, new)
        return Response(code, media_type=JS, headers={"Cache-Control": "no-cache"})
    return _file(p)


@router.get("/files/{name:path}", include_in_schema=False)
async def avatar_file(name: str):
    """Bodies and garments made by BO9 (presets/*.glb, smplx_body.glb, garments/*.glb, users/*)."""
    return _file(_inside(ROOT, name))


@router.get("/garment/{name}.glb", include_in_schema=False)
async def garment(
    name: str, user: str = "usr_042", top: str = "", bottom: str = "", topc: str = "", bottomc: str = ""
):
    """BO9's garment worn as the picked piece: its shape (rules) and its photo (M1), see avatar_dress.py."""
    if name not in GARMENT_SLOT:
        raise HTTPException(404, "not found")
    no_cache = {"Cache-Control": "no-cache"}
    if name == "vest":  # BO9's vest mesh is only half built for now: an empty model, so nothing is worn
        return Response(EMPTY_GLB, media_type="model/gltf-binary", headers=no_cache)
    top_piece, bottom_piece = _piece(user, top), _piece(user, bottom)
    one_piece = top_piece and top_piece["category"] in ("dress", "traditional")
    if name == "shorts" and one_piece and not bottom_piece:  # a dress or a jebba: no shorts under it
        return Response(EMPTY_GLB, media_type="model/gltf-binary", headers=no_cache)
    piece = top_piece if name == "shirt" else bottom_piece
    data = _inside(ROOT, f"garments/{name}.glb").read_bytes()
    if piece:
        from bo.bo7_sharing.avatar_dress import dress_glb, shape_for

        photo = _open(piece["image"])
        shape = shape_for(name, piece["category"], piece["name"])
        data = dress_glb(data, rgb=_rgb(piece["color"]), photo=photo, shape=shape)
    elif _rgb(topc if name == "shirt" else bottomc):
        data = recolor_glb(data, _rgb(topc if name == "shirt" else bottomc))
    return Response(data, media_type="model/gltf-binary", headers=no_cache)


def _rgb(hex_color: str | None) -> tuple[int, int, int] | None:
    h = (hex_color or "").strip().lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4)) if re.fullmatch(r"[0-9a-fA-F]{6}", h) else None


def _open(path: str | None):
    from PIL import Image

    try:
        return Image.open(path) if path and Path(path).is_file() else None
    except OSError:
        return None


def _piece(user: str, item_id: str) -> dict | None:
    """The user's piece (M1, through M15's wardrobe provider): name, category, photo, colour."""
    if not item_id:
        return None
    try:
        from modules.m15_challenges.singleton import challenges_agent

        for g in challenges_agent.wardrobe.items(user):
            if g.item_id == item_id:
                main = max(g.colors, key=lambda c: c.share) if g.colors else None
                return {
                    "name": g.subcategory or g.category.value,
                    "category": g.category.value,
                    "image": g.image_cutout,
                    "color": main.hex if main else None,
                }
    except Exception:  # noqa: BLE001 — wardrobe unavailable: the garment keeps BO9's look
        return None
    return None


def _empty_glb() -> bytes:
    js = json.dumps({"asset": {"version": "2.0"}, "scenes": [{"nodes": []}], "scene": 0}).encode()
    js += b" " * (-len(js) % 4)
    return struct.pack("<III", 0x46546C67, 2, 20 + len(js)) + struct.pack("<II", len(js), 0x4E4F534A) + js


EMPTY_GLB = _empty_glb()


def recolor_glb(glb: bytes, rgb: tuple[int, int, int]) -> bytes:
    """Same GLB, its base-colour texture tinted to `rgb` (folds and shading kept)."""
    from bo.bo7_sharing.avatar_dress import dress_glb

    return dress_glb(glb, rgb=rgb)


@router.get("/status")
async def status(user_id: str = "usr_042") -> dict:
    """What the Flutter screen can use: the viewer, the bodies BO9 generated, and M9's rendered image."""
    presets = sorted(p.name for p in (ROOT / "presets").glob("*.glb")) if (ROOT / "presets").exists() else []
    return {
        "viewer": (VIEWER / "index.html").exists(),
        "viewer_url": viewer_url(presets),
        "bodies": presets + [b for b in ("smplx_body.glb", "smplx_thin.glb") if (ROOT / b).exists()],
        "garments": sorted(n for n in GARMENT_SLOT if (ROOT / "garments" / f"{n}.glb").exists()),
        "m9": m9_render(user_id),
    }


def viewer_url(presets: list[str]) -> str:
    """The viewer opens the body given in ?mesh= (as BO9's shell does): smplx_body.glb, else a preset."""
    if (ROOT / "smplx_thin.glb").exists() and (ROOT / "garments").exists():
        return "/bo7/avatar/viewer/?mesh=/smplx_thin.glb"  # the body BO9's garments were made for
    if (ROOT / "smplx_body.glb").exists():
        return "/bo7/avatar/viewer/?mesh=/smplx_body.glb"
    if presets:
        first = "female_average.glb" if "female_average.glb" in presets else presets[0]
        return f"/bo7/avatar/viewer/?mesh=/presets/{first}"
    return "/bo7/avatar/viewer/"


def m9_render(user_id: str) -> dict:
    """Rendered avatar from M9 (BO9's module), through its public function. None while M9 is a mock."""
    try:
        from modules.m09_avatar_3d import mock, service
        from shared.config import settings

        impl = mock if getattr(settings, "use_mocks", True) else service
        res = impl.render({"user_id": user_id, "payload": {"view": "front", "format": "png"}})
    except Exception as e:  # noqa: BLE001 — M9 not ready: BO7 keeps working with the viewer picture
        return {"image": None, "mocked": True, "note": f"M9 unavailable: {type(e).__name__}"}
    result = res.get("result") or {}
    image = result.get("image") or result.get("image_url")
    note = None if image else "M9 is a mock (no image)"
    return {"image": image, "mocked": bool(res.get("mocked")), "note": note}
