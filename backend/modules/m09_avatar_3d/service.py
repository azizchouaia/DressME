"""Real implementation of M9: pieces from phone photos + avatar rendering (GLB). No model is trained.

Pieces: photos are stored, then ml/scripts/m09/garment_photo.py runs in its own Python env (ml/.venv: rembg /
BiRefNet + numpy 2, isolated from the backend) and writes the texture atlas + info.json next to them.
Rendering: Blender runs headless (`blender -b --python ml/blender/build_avatar.py -- spec.json`) with the MPFB
add-on and the CC0 MakeHuman asset packs; one render at a time; results cached by the hash of the spec.

Config (env): M09_BLENDER (blender executable), M09_SEG_PYTHON (python of ml/.venv), M09_DATA (storage dir).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import threading
import uuid
from pathlib import Path

from .contract import PieceSheet, RenderPayload

REPO = Path(__file__).resolve().parents[3]
BLENDER_DIR = REPO / "ml" / "blender"
SEG_SCRIPT = REPO / "ml" / "scripts" / "m09" / "garment_photo.py"
DATA = Path(os.environ.get("M09_DATA", Path(__file__).parent / ".data"))
BLENDER = os.environ.get("M09_BLENDER") or shutil.which("blender") or r"C:\MLDLEXT\blender\blender.exe"
SEG_PYTHON = os.environ.get("M09_SEG_PYTHON") or str(REPO / "ml" / ".venv" / "Scripts" / "python.exe")
RENDER_VERSION = "2"  # bump to invalidate cached renders after a change of the Blender pipeline
_render_lock = threading.Lock()

KIND_OF = {
    "pants": "bottom",
    "jeans": "bottom",
    "cargo pants": "bottom",
    "shorts": "bottom",
    "skirt": "bottom",
    "dress": "dress",
    "jacket": "outerwear",
    "blazer": "outerwear",
    "shoes": "shoes",
}


def _ok(result: dict) -> dict:
    return {"result": result, "mocked": False}


def _uid(user_id: str | None) -> str:
    return "".join(c for c in (user_id or "anonymous") if c.isalnum() or c in "-_")[:64] or "anonymous"


def _piece_dir(user: str, pid: str) -> Path:
    return DATA / "pieces" / user / pid


def file_url(path: Path) -> str:
    return "/m09/files/" + path.relative_to(DATA).as_posix()


def _public(p: dict) -> dict:
    d = _piece_dir(p["user_id"], p["piece_id"])
    out = {**p}
    for k in ("front", "back", "atlas"):
        f = d / {"front": "front_input.jpg", "back": "back.jpg", "atlas": "atlas.png"}[k]
        out[f"{k}_url"] = file_url(f) if f.exists() else None
    return out


# ---------------- pieces ----------------
def create_piece(
    user_id: str | None,
    sheet: PieceSheet,
    front: bytes | None,
    back: bytes | None,
    front_ext: str = ".jpg",
    back_ext: str = ".jpg",
) -> dict:
    user, pid = _uid(user_id), uuid.uuid4().hex[:12]
    d = _piece_dir(user, pid)
    d.mkdir(parents=True, exist_ok=True)
    rec = {
        "piece_id": pid,
        "user_id": user,
        "sheet": sheet.model_dump(),
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "photo": bool(front),
        "main_color": sheet.color,
        "status": "ready",
    }
    if front:
        # raw uploads keep their own names: garment_photo.py writes front_input.jpg (shown by the page)
        (d / f"upload_front{front_ext}").write_bytes(front)
        cmd = [
            SEG_PYTHON,
            str(SEG_SCRIPT),
            "--front",
            str(d / f"upload_front{front_ext}"),
            "--kind",
            KIND_OF.get(sheet.type.lower(), "top"),
            "--type",
            sheet.type,
            "--out",
            str(d),
        ]
        if sheet.length:
            cmd += ["--length", sheet.length]
        if back:
            (d / f"upload_back{back_ext}").write_bytes(back)
            cmd += ["--back", str(d / f"upload_back{back_ext}")]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        except (OSError, subprocess.TimeoutExpired) as e:
            shutil.rmtree(d, ignore_errors=True)
            raise ValueError(f"photo processing failed: {e}") from e
        if back and not (d / "back.jpg").exists():
            shutil.copy(d / f"upload_back{back_ext}", d / "back.jpg")
        info = d / "info.json"
        if proc.returncode != 0 or not info.exists():
            shutil.rmtree(d, ignore_errors=True)
            raise ValueError("photo processing failed: " + (proc.stderr or proc.stdout)[-600:])
        i = json.loads(info.read_text())
        rec.update(
            main_color=i["main_color"], sleeve_color=i.get("sleeve_color"), has_back_photo=i["has_back_photo"]
        )
    else:
        if not sheet.color:
            rec["main_color"] = sheet.color = "#808080"
            rec["sheet"]["color"] = "#808080"
        make_pattern(d, rec["sheet"])
    (d / "piece.json").write_text(json.dumps(rec, indent=1))
    _built_3d(user)
    return _ok({"piece": _public(rec)})


def _built_3d(user: str) -> None:
    """A saved / changed piece gets its 3D version built in the background for the user's body."""
    from . import wardrobe3d

    if wardrobe3d.profile(user) is not None:
        wardrobe3d.request(user)


def make_pattern(d: Path, sheet: dict) -> None:
    """Sewing pattern of a piece (pattern.json + pattern_atlas.png) for the cloth simulation: from its photos
    (re-run of the photo pipeline) or, without photo, the default pattern of its type in its colour."""
    kind = KIND_OF.get(sheet["type"].lower(), "top")
    if kind == "shoes":
        return
    fr = sorted(d.glob("upload_front.*"))
    if fr:
        cmd = [
            SEG_PYTHON,
            str(SEG_SCRIPT),
            "--front",
            str(fr[0]),
            "--kind",
            kind,
            "--type",
            sheet["type"],
            "--out",
            str(d),
        ]
        bk = sorted(d.glob("upload_back.*"))
        if bk:
            cmd += ["--back", str(bk[0])]
    else:
        cmd = [
            SEG_PYTHON,
            str(SEG_SCRIPT),
            "--colour",
            sheet.get("color") or "#808080",
            "--kind",
            kind,
            "--type",
            sheet["type"],
            "--out",
            str(d),
        ]
    if sheet.get("length"):
        cmd += ["--length", sheet["length"]]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except (OSError, subprocess.TimeoutExpired):
        pass


def list_pieces(user_id: str | None) -> dict:
    root = DATA / "pieces" / _uid(user_id)
    out = []
    if root.exists():
        for f in root.glob("*/piece.json"):
            out.append(_public(json.loads(f.read_text())))
    out.sort(key=lambda p: p["created_at"], reverse=True)
    return _ok({"pieces": out})


def delete_piece(user_id: str | None, piece_id: str) -> dict:
    d = _piece_dir(_uid(user_id), "".join(c for c in piece_id if c.isalnum()))
    if not (d / "piece.json").exists():
        return _ok({"deleted": False})
    shutil.rmtree(d, ignore_errors=True)
    return _ok({"deleted": True})


def update_piece(user_id: str | None, piece_id: str, sheet: PieceSheet) -> dict:
    d = _piece_dir(_uid(user_id), "".join(c for c in piece_id if c.isalnum()))
    f = d / "piece.json"
    if not f.exists():
        raise ValueError("unknown piece")
    rec = json.loads(f.read_text())
    old = rec["sheet"]
    rec["sheet"] = sheet.model_dump()
    if any(old.get(k) != rec["sheet"].get(k) for k in ("type", "length", "color")):
        make_pattern(d, rec["sheet"])  # another type / length / colour = another pattern
    f.write_text(json.dumps(rec, indent=1))
    _built_3d(rec["user_id"])
    return _ok({"piece": _public(rec)})


# ---------------- rendering ----------------
def _spec(user: str, p: RenderPayload) -> dict:
    outfit = []
    for pid in p.piece_ids:
        f = _piece_dir(user, "".join(c for c in pid if c.isalnum())) / "piece.json"
        if not f.exists():
            raise ValueError(f"unknown piece {pid}")
        rec = json.loads(f.read_text())
        s = rec["sheet"]
        piece = {"type": s["type"]}
        for k in ("size", "fit", "gsm", "length", "sleeves"):
            if s.get(k):
                piece[k] = s[k]
        if rec.get("photo"):
            piece["texture"] = str(f.parent / "info.json")
        else:
            piece["color"] = s.get("color") or "#808080"
        if s["type"] == "shoes":
            piece.pop("size", None)
        outfit.append(piece)
    if not any(x["type"] == "shoes" for x in outfit):
        outfit.append({"type": "shoes", "color": "#e8e4dc"})
    return {"sex": p.sex, "height_cm": p.height_cm, "weight_kg": p.weight_kg, "outfit": outfit}


def render(req: dict) -> dict:
    p = RenderPayload.model_validate(req.get("payload") or {})
    user = _uid(req.get("user_id"))
    spec = _spec(user, p)
    key = hashlib.sha1((RENDER_VERSION + json.dumps(spec, sort_keys=True)).encode()).hexdigest()[:16]
    out = DATA / "renders" / f"{key}.glb"
    meta = out.with_suffix(".json")
    if out.exists() and meta.exists():
        return _ok({**json.loads(meta.read_text()), "glb_url": file_url(out), "cached": True})
    out.parent.mkdir(parents=True, exist_ok=True)
    spec["out"] = str(out)
    spec_file = out.with_suffix(".spec.json")
    spec_file.write_text(json.dumps(spec))
    if not Path(BLENDER).exists():
        raise ValueError(f"Blender not found at {BLENDER} (set M09_BLENDER)")
    with _render_lock:  # one Blender at a time
        t0 = dt.datetime.now()
        proc = subprocess.run(
            [
                BLENDER,
                "-b",
                "-noaudio",
                "--python",
                str(BLENDER_DIR / "build_avatar.py"),
                "--",
                str(spec_file),
            ],
            capture_output=True,
            text=True,
            timeout=900,
        )
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("BUILD_RESULT ")), None)
    if proc.returncode != 0 or line is None or not out.exists():
        raise ValueError("render failed: " + (proc.stderr or proc.stdout)[-800:])
    res = json.loads(line[len("BUILD_RESULT ") :])
    info = {
        "body": res.get("body"),
        "fit": res.get("fit"),
        "garments": res.get("garments"),
        "seconds": round((dt.datetime.now() - t0).total_seconds(), 1),
        "sizing": {
            k: {kk: v.get(kk) for kk in ("scale_width", "scale_length", "target") if kk in v}
            for k, v in (res.get("sizing") or {}).items()
        },
    }
    meta.write_text(json.dumps(info))
    return _ok({**info, "glb_url": file_url(out), "cached": False})


def options() -> dict:
    import sys

    if str(BLENDER_DIR) not in sys.path:
        sys.path.insert(0, str(BLENDER_DIR))
    import templates  # plain Python (no bpy)

    types = sorted({k.split("_")[0] for k in templates.T} | {"skirt"})
    from .contract import FITS, LENGTHS, SIZES, SLEEVES

    return {
        "types": [t for t in types if t != "skirt_mini"],
        "sizes": list(SIZES),
        "fits": list(FITS),
        "lengths": list(LENGTHS),
        "sleeves": list(SLEEVES),
        "gsm_defaults": {k: v["gsm"] for k, v in templates.T.items()},
        "blender": {"path": BLENDER, "found": Path(BLENDER).exists()},
        "segmentation_python": {"path": SEG_PYTHON, "found": Path(SEG_PYTHON).exists()},
    }
