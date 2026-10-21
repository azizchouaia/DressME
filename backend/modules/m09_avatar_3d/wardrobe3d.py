"""Ready-to-wear 3D wardrobe: every saved piece already exists in 3D, fitted to the user's body.

The viewer loads the bare body + one GLB per garment and puts garments on / off instantly (no render at try-on
time). Each garment is fitted alone on the body at its own distance from the skin (outer layers further out),
so any combination works.

Files (under service.DATA):
    profiles/<user>.json                      body of the user: sex, height_cm, weight_kg
    bodies/<body key>/body.glb                bare faceless body
    bodies/<body key>/<piece id>_<sheet key>.glb   one garment fitted to that body (new sheet -> new file)
    bodies/<body key>/errors.json             pieces that failed for this body

A single background worker runs Blender (one process for the body + up to CHUNK garments), so saving a piece
or changing the body queues work and the page polls GET /m09/wardrobe3d until everything is ready.
"""

from __future__ import annotations

import hashlib
import json
import logging
import queue
import subprocess
import threading
from pathlib import Path

import numpy as np

from . import service
from .contract import Body

log = logging.getLogger("m09.wardrobe3d")
VERSION = "11"  # bump when the Blender pipeline changes: every garment is rebuilt
CHUNK = 6  # garments per Blender run (results show up chunk by chunk)
SLOT = {"top": "top", "bottom": "bottom", "dress": "dress", "outerwear": "outerwear", "shoes": "shoes"}
TOP_TYPES = {
    "t-shirt",
    "jersey",
    "top",
    "blouse",
    "polo shirt",
    "shirt",
    "long-sleeve top",
    "sweater",
    "hoodie",
    "short-sleeve shirt",
}

_q: queue.Queue[str] = queue.Queue()
_pending: set[str] = set()
_building: dict[str, list[str]] = {}  # user -> ids in the running Blender
_lock = threading.Lock()
_worker: threading.Thread | None = None


# ---------------- keys and paths ----------------
def kind_of(piece_type: str) -> str:
    t = piece_type.lower()
    if t in service.KIND_OF:
        return service.KIND_OF[t]
    return "top"


def profile(user: str) -> Body | None:
    f = service.DATA / "profiles" / f"{user}.json"
    return Body.model_validate_json(f.read_text()) if f.exists() else None


def set_profile(user: str, body: Body) -> Body:
    f = service.DATA / "profiles" / f"{user}.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    body = Body(sex=body.sex, height_cm=round(body.height_cm), weight_kg=round(body.weight_kg))
    f.write_text(body.model_dump_json())
    return body


def body_key(b: Body) -> str:
    return hashlib.sha1(f"{VERSION}|{b.sex}|{round(b.height_cm)}|{round(b.weight_kg)}".encode()).hexdigest()[
        :12
    ]


def body_dir(b: Body) -> Path:
    return service.DATA / "bodies" / body_key(b)


def piece_key(rec: dict) -> str:
    """Changes when the sheet or the photo processing changes (re-processed photo -> new info.json)."""
    d = service._piece_dir(rec["user_id"], rec["piece_id"])
    stamp = "|".join(
        str(int(f.stat().st_mtime)) if f.exists() else "-" for f in (d / "info.json", d / "pattern.json")
    )
    return hashlib.sha1(json.dumps([rec["sheet"], stamp], sort_keys=True).encode()).hexdigest()[:10]


def piece_glb(b: Body, rec: dict) -> Path:
    return body_dir(b) / f"{rec['piece_id']}_{piece_key(rec)}.glb"


def _errors(b: Body) -> dict:
    f = body_dir(b) / "errors.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _records(user: str) -> list[dict]:
    root = service.DATA / "pieces" / user
    out = [json.loads(f.read_text()) for f in root.glob("*/piece.json")] if root.exists() else []
    return sorted(out, key=lambda r: r["created_at"])


# ---------------- state for the page ----------------
def state(user_id: str | None) -> dict:
    user = service._uid(user_id)
    b = profile(user)
    building = _building.get(user, [])
    pieces = []
    errs = _errors(b) if b else {}
    for rec in reversed(_records(user)):
        p = service._public(rec)
        d = service._piece_dir(user, rec["piece_id"])
        cut = d / "cutout.png"
        p["cutout_url"] = service.file_url(cut) if cut.exists() else p.get("front_url")
        p["kind"] = kind_of(rec["sheet"]["type"])
        p["slot"] = SLOT.get(p["kind"], "top")
        p["glb_url"], p["status3d"] = None, "no body"
        if b:
            glb = piece_glb(b, rec)
            if glb.exists():
                p["glb_url"], p["status3d"] = service.file_url(glb), "ready"
            elif errs.get(glb.name):
                p["status3d"], p["error3d"] = "failed", errs[glb.name]
            else:
                p["status3d"] = "building" if rec["piece_id"] in building else "queued"
        pieces.append(p)
    body = None
    if b:
        g = body_dir(b) / "body.glb"
        body = {**b.model_dump(), "key": body_key(b), "glb_url": service.file_url(g) if g.exists() else None}
    busy = user in _pending or bool(building) or any(p["status3d"] in ("queued", "building") for p in pieces)
    if busy and user not in _pending and not building:
        request(user)  # something is missing and nobody is on it (server restarted): queue it
    return {"body": body, "pieces": pieces, "busy": busy}


# ---------------- background builds ----------------
def request(user: str) -> None:
    global _worker
    with _lock:
        if user not in _pending:
            _pending.add(user)
            _q.put(user)
        if _worker is None or not _worker.is_alive():
            _worker = threading.Thread(target=_loop, name="m09-wardrobe3d", daemon=True)
            _worker.start()


def _loop() -> None:
    while True:
        user = _q.get()
        with _lock:
            _pending.discard(user)
        try:
            _build_missing(user)
        except Exception:  # noqa: BLE001
            log.exception("3D wardrobe build failed for %s", user)
        finally:
            _building.pop(user, None)


def _piece_spec(rec: dict) -> dict:
    s = rec["sheet"]
    spec = {"type": s["type"]}
    for k in ("size", "fit", "gsm", "length", "sleeves"):
        if s.get(k):
            spec[k] = s[k]
    d = service._piece_dir(rec["user_id"], rec["piece_id"])
    if rec.get("photo") and (d / "info.json").exists():
        spec["texture"] = str(d / "info.json")
    else:
        spec["color"] = s.get("color") or "#808080"
    if (d / "pattern.json").exists():  # sewn from its pattern with cloth physics
        spec["pattern"] = str(d / "pattern.json")
    if s["type"] == "shoes":
        spec.pop("size", None)
    return spec


def _build_missing(user: str) -> None:
    for _ in range(50):  # pieces added while building are picked up by the next round
        b = profile(user)
        if b is None:
            return
        d = body_dir(b)
        d.mkdir(parents=True, exist_ok=True)
        errs = _errors(b)
        need_body = not (d / "body.glb").exists()
        todo = [
            r for r in _records(user) if not piece_glb(b, r).exists() and piece_glb(b, r).name not in errs
        ]
        if not need_body and not todo:
            return
        chunk = todo[:CHUNK]
        spec = {
            "mode": "parts",
            **b.model_dump(),
            "body_out": str(d / "body.glb") if need_body else None,
            "pieces": [{"id": r["piece_id"], "out": str(piece_glb(b, r)), **_piece_spec(r)} for r in chunk],
        }
        spec_file = d / f"spec_{user}.json"
        spec_file.write_text(json.dumps(spec))
        _building[user] = [r["piece_id"] for r in chunk]
        with service._render_lock:
            proc = subprocess.run(
                [
                    service.BLENDER,
                    "-b",
                    "-noaudio",
                    "--python",
                    str(service.BLENDER_DIR / "build_avatar.py"),
                    "--",
                    str(spec_file),
                ],
                capture_output=True,
                text=True,
                timeout=1800,
            )
        done = {}
        for ln in proc.stdout.splitlines():
            if ln.startswith("PART_DONE "):
                r = json.loads(ln[len("PART_DONE ") :])
                done[r["id"]] = r
        for r in chunk:  # a piece that did not come out is marked failed (no endless retries)
            glb = piece_glb(b, r)
            if not glb.exists():
                errs[glb.name] = (
                    done.get(r["piece_id"], {}).get("error") or (proc.stderr or proc.stdout)[-300:]
                )
        (d / "errors.json").write_text(json.dumps(errs, indent=1))
        if need_body and not (d / "body.glb").exists():
            log.error("body build failed: %s", (proc.stderr or proc.stdout)[-500:])
            return


# ---------------- FashionCLIP vectors for M2 ----------------
PALETTE = {
    "black": (25, 25, 25),
    "white": (240, 240, 240),
    "grey": (128, 128, 128),
    "light grey": (190, 190, 190),
    "navy": (30, 40, 80),
    "blue": (50, 90, 180),
    "light blue": (140, 180, 225),
    "red": (190, 30, 40),
    "burgundy": (110, 25, 40),
    "pink": (230, 150, 180),
    "orange": (235, 130, 40),
    "yellow": (235, 210, 60),
    "beige": (215, 195, 160),
    "brown": (115, 75, 45),
    "green": (50, 130, 60),
    "olive": (110, 110, 50),
    "khaki": (170, 160, 110),
    "purple": (110, 60, 150),
}


def colour_name(hexcol: str) -> str:
    h = (hexcol or "#808080").lstrip("#")
    rgb = np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], float)
    return min(PALETTE, key=lambda n: float(((np.array(PALETTE[n]) - rgb) ** 2).sum()))


def description(rec: dict) -> str:
    s = rec["sheet"]
    t = s["type"]
    if s.get("length") and t == "skirt":
        t = f"{s['length']} skirt"
    if s.get("sleeves") and t in TOP_TYPES:
        t = f"{s['sleeves']}-sleeve {t}"
    return f"{colour_name(rec.get('main_color') or s.get('color'))} {t}"


def embedding(rec: dict) -> list[float]:
    """1024 floats = [FashionCLIP image (cut-out on white) | FashionCLIP text of the description], the item
    vector M2's pretrained OutfitTransformer expects (the same encoder M2 uses). Cached next to the piece.
    A piece without photo uses its text vector for both halves."""
    d = service._piece_dir(rec["user_id"], rec["piece_id"])
    desc = description(rec)
    f = d / "embedding.json"
    if f.exists():
        cached = json.loads(f.read_text())
        if cached.get("description") == desc:
            return cached["vector"]
    from PIL import Image

    from modules.m02_recommendation.engine import encoder

    txt = encoder.embed_texts([desc])[0]
    cut = d / "cutout.png"
    if cut.exists():
        im = Image.open(cut).convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        img = encoder.embed_images([Image.alpha_composite(bg, im).convert("RGB")])[0]
    else:
        img = txt
    vec = [float(x) for x in np.concatenate([img, txt])]
    f.write_text(json.dumps({"description": desc, "vector": vec}))
    return vec


def category(rec: dict) -> str:
    k = kind_of(rec["sheet"]["type"])
    return {"top": "top", "bottom": "bottom", "dress": "dress", "outerwear": "outerwear", "shoes": "shoes"}[k]


def wardrobe_items(user: str) -> list[dict]:
    """The user's pieces in M1's Garment format (+ FashionCLIP vector), ready for M2 / M17."""
    out = []
    for rec in _records(user):
        d = service._piece_dir(user, rec["piece_id"])
        hexcol = rec.get("main_color") or rec["sheet"].get("color") or "#808080"
        out.append(
            {
                "item_id": rec["piece_id"],
                "user_id": user,
                "image_raw": service.file_url(d / "front_input.jpg")
                if (d / "front_input.jpg").exists()
                else "",
                "image_cutout": service.file_url(d / "cutout.png") if (d / "cutout.png").exists() else None,
                "category": category(rec),
                "subcategory": rec["sheet"]["type"],
                "colors": [{"name": colour_name(hexcol), "hex": hexcol, "share": 1.0}],
                "embedding": embedding(rec),
            }
        )
    return out


# ---------------- outfits worn together (cloth physics) + turn animation ----------------
OUTFIT_VERSION = "3"
_oq: queue.Queue[tuple] = queue.Queue()
_opending: dict[str, str] = {}  # outfit key -> "queued" / "building"
_oworker: threading.Thread | None = None


def outfit_key(b: Body, recs: list[dict], animate: bool) -> str:
    parts = sorted(f"{r['piece_id']}_{piece_key(r)}" for r in recs)
    raw = f"{OUTFIT_VERSION}|{body_key(b)}|{'+'.join(parts)}|{int(animate)}"
    return hashlib.sha1(raw.encode()).hexdigest()[:14]


def outfit_dir(b: Body, key: str) -> Path:
    return body_dir(b) / "outfits" / key


def outfit(user_id: str | None, piece_ids: list[str], animate: bool = False) -> dict:
    """The pieces worn together: each garment re-fitted over the ones under it (Blender cloth), cached per
    combination; with `animate`, the turn animation too. Queued in the background, the page polls this."""
    user = service._uid(user_id)
    b = profile(user)
    if b is None:
        raise ValueError("create your avatar first")
    by_id = {r["piece_id"]: r for r in _records(user)}
    recs = [by_id[i] for i in piece_ids if i in by_id]
    if len(recs) < 2 and not animate:
        return {"status": "single", "pieces": {}}
    key = outfit_key(b, recs, animate)
    d = outfit_dir(b, key)
    done = d / "done.json"
    if done.exists():
        info = json.loads(done.read_text())
        res = {
            "status": "ready" if info.get("ok") else "failed",
            "key": key,
            "error": info.get("error"),
            "pieces": {
                i: service.file_url(d / f"{i}.glb")
                for i in info.get("pieces", [])
                if (d / f"{i}.glb").exists()
            },
        }
        meta = d / "anim" / "anim.json"
        if animate and meta.exists():
            m = json.loads(meta.read_text())
            res["animation"] = {
                **m,
                "urls": {i: service.file_url(d / "anim" / f"{i}.glb") for i in m["pieces"]},
            }
        return res
    status = _opending.get(key)
    if status is None:
        _opending[key] = "queued"
        _oq.put((user, b, [r["piece_id"] for r in recs], animate, key))
        _start_outfit_worker()
        status = "queued"
    return {"status": status, "key": key, "pieces": {}}


def _start_outfit_worker() -> None:
    global _oworker
    with _lock:
        if _oworker is None or not _oworker.is_alive():
            _oworker = threading.Thread(target=_outfit_loop, name="m09-outfit3d", daemon=True)
            _oworker.start()


def _outfit_loop() -> None:
    while True:
        user, b, ids, animate, key = _oq.get()
        try:
            _opending[key] = "building"
            _build_outfit(user, b, ids, animate, key)
        except Exception as e:  # noqa: BLE001
            log.exception("outfit build failed")
            d = outfit_dir(b, key)
            d.mkdir(parents=True, exist_ok=True)
            (d / "done.json").write_text(json.dumps({"ok": False, "error": str(e)[:300]}))
        finally:
            _opending.pop(key, None)


def _build_outfit(user: str, b: Body, ids: list[str], animate: bool, key: str) -> None:
    d = outfit_dir(b, key)
    d.mkdir(parents=True, exist_ok=True)
    by_id = {r["piece_id"]: r for r in _records(user)}
    pieces = []
    for i in ids:
        r = by_id[i]
        pieces.append(
            {"id": i, "out": str(d / f"{i}.glb"), "kind": kind_of(r["sheet"]["type"]), **_piece_spec(r)}
        )
    spec = {
        "mode": "parts",
        "outfit": True,
        "animate": animate,
        "anim_dir": str(d / "anim"),
        **b.model_dump(),
        "body_out": None,
        "pieces": pieces,
    }
    spec_file = d / "spec.json"
    spec_file.write_text(json.dumps(spec))
    with service._render_lock:
        proc = subprocess.run(
            [
                service.BLENDER,
                "-b",
                "-noaudio",
                "--python",
                str(service.BLENDER_DIR / "build_avatar.py"),
                "--",
                str(spec_file),
            ],
            capture_output=True,
            text=True,
            timeout=1800,
        )
    ok_ids = []
    for ln in proc.stdout.splitlines():
        if ln.startswith("PART_DONE "):
            r = json.loads(ln[len("PART_DONE ") :])
            if r.get("ok") and (d / f"{r['id']}.glb").exists():
                ok_ids.append(r["id"])
    ok = len(ok_ids) == len(ids)
    (d / "done.json").write_text(
        json.dumps({"ok": ok, "pieces": ok_ids, "error": None if ok else (proc.stderr or proc.stdout)[-300:]})
    )
