"""Backend for the DressMe studio page (avatar_studio/web/studio).

A user is made once: name, gender, height, weight, and a front and a back
photo. The photos go through garment_pipeline.py with --avatar, which gives
the person's avatar (face, skin tone, hair colour, hairstyle) and the outfit
they wore. After that, every new pair of photos only builds the clothes, fitted
to the same avatar. A finished build waits as a draft until it is saved to the
user's wardrobe.

    py -3 ai/remu/studio_server.py        (http://127.0.0.1:8893)

Files, all under avatar_studio/web/avatars/USER:
    user.json                 name, gender, height, weight, hairstyle
    avatar.glb, profile.json  written by photo_avatar.py
    photos/front, photos/back the last uploaded pair
    outfits/_draft/           the last build, not saved yet
    outfits/ID/               saved outfits: shirt.glb, pants.glb, photo.jpg, outfit.json
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "avatar_studio" / "web"
AVATARS = WEB / "avatars"
RECO = WEB / "garments" / "saved" / "reco"
WORK = WEB / "garments" / "saved" / "pipeline"
LAST_PHOTOS = WORK / "last_photos.json"
PIPELINE = ROOT / "ai" / "remu" / "garment_pipeline.py"
PIECES = ("shirt.glb", "pants.glb")
DRAFT = "_draft"
MAX_BYTES = 20 * 1024 * 1024
PORT = 8893

STEPS = [
    ("checking and framing", "Checking the photos"),
    ("uploading the photos", "Uploading to the GPU"),
    ("starting the T4", "Reconstructing in 3D (about 20 minutes)"),
    ("downloading", "Downloading the 3D result"),
    ("cutting the shirt", "Fitting the clothes to the avatar"),
    ("picking the hairstyle", "Choosing a hairstyle"),
    ("saving the face", "Printing the face and skin tone"),
    ("done:", "Done"),
]

job: dict = {"busy": False}
job_lock = threading.Lock()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "user"


def _user_dir(user: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]{1,40}", user or ""):
        raise ValueError("Unknown user.")
    return AVATARS / user


def _read(path: Path, fallback=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else fallback


def _write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _outfit(folder: Path, user: str) -> dict:
    meta = _read(folder / "outfit.json", {})
    stamp = int(max(p.stat().st_mtime for p in folder.iterdir()))
    return {
        "id": folder.name,
        "name": meta.get("name", folder.name),
        "created": meta.get("created"),
        "pieces": [f"/avatars/{user}/outfits/{folder.name}/{piece}?v={stamp}" for piece in PIECES if (folder / piece).is_file()],
        "photo": f"/avatars/{user}/outfits/{folder.name}/photo.jpg?v={stamp}" if (folder / "photo.jpg").is_file() else None,
    }


def user_view(user: str) -> dict:
    folder = _user_dir(user)
    info = _read(folder / "user.json")
    if info is None:
        raise ValueError("Unknown user.")
    profile = _read(folder / "profile.json")
    outfits_dir = folder / "outfits"
    saved = []
    if outfits_dir.is_dir():
        for item in sorted(outfits_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if item.is_dir() and item.name != DRAFT and (item / "outfit.json").is_file():
                saved.append(_outfit(item, user))
    draft = outfits_dir / DRAFT
    stamp = int((folder / "avatar.glb").stat().st_mtime) if (folder / "avatar.glb").is_file() else 0
    return {
        **info,
        "ready": profile is not None,
        "avatar": f"/avatars/{user}/avatar.glb?v={stamp}" if profile else None,
        "profile": profile,
        "outfits": saved,
        "draft": _outfit(draft, user) if (draft / PIECES[0]).is_file() else None,
    }


def list_users() -> list[dict]:
    users = []
    if AVATARS.is_dir():
        for folder in sorted(AVATARS.iterdir()):
            if (folder / "user.json").is_file():
                users.append(user_view(folder.name))
    return users


def create_user(body: dict) -> dict:
    name = str(body.get("name", "")).strip()
    gender = body.get("gender")
    height, weight = float(body.get("height", 0)), float(body.get("weight", 0))
    if not name:
        raise ValueError("Enter a name.")
    if gender not in ("male", "female"):
        raise ValueError("Choose male or female.")
    if body.get("shape", "average") not in ("slim", "average", "athletic", "heavy"):
        raise ValueError("Choose a body shape.")
    if not 120 <= height <= 230:
        raise ValueError("Height should be between 120 and 230 cm.")
    if not 30 <= weight <= 250:
        raise ValueError("Weight should be between 30 and 250 kg.")
    user = _slug(name)
    base, count = user, 2
    while (AVATARS / user / "user.json").exists():
        user, count = f"{base}-{count}", count + 1
    _write(AVATARS / user / "user.json", {"id": user, "name": name, "gender": gender, "height": height, "weight": weight, "shape": body.get("shape", "average"), "hair": None, "created": time.strftime("%Y-%m-%d %H:%M")})
    return user_view(user)


def update_user(user: str, body: dict) -> dict:
    path = _user_dir(user) / "user.json"
    info = _read(path)
    if info is None:
        raise ValueError("Unknown user.")
    if "hair" in body:
        info["hair"] = body["hair"] or None
    if "height" in body:
        height = float(body["height"])
        if not 120 <= height <= 230:
            raise ValueError("Height should be between 120 and 230 cm.")
        info["height"] = height
    if "weight" in body:
        weight = float(body["weight"])
        if not 30 <= weight <= 250:
            raise ValueError("Weight should be between 30 and 250 kg.")
        info["weight"] = weight
    if "shape" in body:
        if body["shape"] not in ("slim", "average", "athletic", "heavy"):
            raise ValueError("Choose a body shape.")
        info["shape"] = body["shape"]
    _write(path, info)
    return user_view(user)


def _digest(user: str, mirror: bool) -> str:
    photos = _user_dir(user) / "photos"
    sha = hashlib.sha256()
    for slot in ("front", "back"):
        sha.update((photos / slot).read_bytes())
    sha.update(b"mirror" if mirror else b"plain")
    return sha.hexdigest()


def _step(line: str) -> str | None:
    lowered = line.lower()
    for key, label in STEPS:
        if key in lowered:
            return label
    return None


def _run(user: str, kind: str, mirror: bool) -> None:
    folder = _user_dir(user)
    info = _read(folder / "user.json")
    photos = folder / "photos"
    command = [sys.executable, str(PIPELINE), str(photos / "front"), str(photos / "back")]
    if mirror:
        command.append("--mirror-front")
    digest = _digest(user, mirror)
    if (_read(LAST_PHOTOS, {}) or {}).get("digest") == digest and (WORK / "run" / "outfit_reco.obj").is_file():
        command.append("--skip-kaggle")
        job["lines"].append("These photos were reconstructed before; reusing that 3D result.")
    if kind == "avatar":
        command += ["--avatar", user, "--gender", info["gender"]]
    try:
        process = subprocess.Popen(command, cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        for raw in process.stdout:
            line = raw.rstrip()
            if not line:
                continue
            job["lines"] = (job["lines"] + [line])[-60:]
            step = _step(line)
            if step:
                job["step"] = step
        if process.wait() != 0:
            tail = [line for line in job["lines"] if line.strip()][-1:] or ["The build stopped."]
            raise RuntimeError(tail[0])
        _write(LAST_PHOTOS, {"digest": digest})
        draft = folder / "outfits" / DRAFT
        shutil.rmtree(draft, ignore_errors=True)
        draft.mkdir(parents=True)
        for piece in PIECES:
            shutil.copy2(RECO / piece, draft / piece)
        shutil.copy2(photos / "front", draft / "photo.jpg")
        _write(draft / "outfit.json", {"name": "New outfit", "created": time.strftime("%Y-%m-%d %H:%M")})
        if kind == "avatar":
            if info.get("hair") is None:
                info["hair"] = ((_read(folder / "profile.json", {}) or {}).get("look") or {}).get("hair")
                _write(folder / "user.json", info)
            save_draft(user, "My first outfit")
        job.update(step="Done", done=True)
    except Exception as exc:  # noqa: BLE001
        job.update(error=str(exc)[:400], step="Stopped")
    finally:
        job["busy"] = False


def start_build(user: str, kind: str, mirror: bool) -> dict:
    folder = _user_dir(user)
    if kind not in ("avatar", "outfit"):
        raise ValueError("Build an avatar or an outfit.")
    if kind == "outfit" and not (folder / "profile.json").is_file():
        raise ValueError("Create the avatar first.")
    missing = [slot for slot in ("front", "back") if not (folder / "photos" / slot).is_file()]
    if missing:
        raise ValueError(f"Add the {' and '.join(missing)} photo.")
    with job_lock:
        if job.get("busy"):
            raise ValueError("Another build is running. Wait for it to finish.")
        job.clear()
        job.update(busy=True, user=user, kind=kind, step="Starting", lines=[], error=None, done=False, started=time.time())
    threading.Thread(target=_run, args=(user, kind, mirror), daemon=True).start()
    return job


def save_draft(user: str, name: str) -> dict:
    outfits = _user_dir(user) / "outfits"
    draft = outfits / DRAFT
    if not (draft / PIECES[0]).is_file():
        raise ValueError("There is no new outfit to save.")
    name = name.strip() or "Outfit"
    target = outfits / f"{_slug(name)}-{time.strftime('%Y%m%d%H%M%S')}"
    meta = _read(draft / "outfit.json", {})
    meta["name"] = name
    _write(draft / "outfit.json", meta)
    draft.rename(target)
    return user_view(user)


def delete_outfit(user: str, outfit: str) -> dict:
    if not re.fullmatch(r"[a-z0-9_-]{1,80}", outfit):
        raise ValueError("Unknown outfit.")
    shutil.rmtree(_user_dir(user) / "outfits" / outfit, ignore_errors=True)
    return user_view(user)


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, data) -> None:
        raw = json.dumps(data).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _route(self, method: str) -> None:
        url = urlparse(self.path)
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        parts = [part for part in url.path.split("/") if part][1:] if url.path.startswith("/api/") else None
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > MAX_BYTES:
            self._send(413, {"error": "The upload is larger than 20 MB."})
            return
        body = self.rfile.read(length) if length else b""
        try:
            if parts is None:
                raise LookupError
            if method == "GET" and parts == ["users"]:
                return self._send(200, list_users())
            if method == "GET" and parts == ["job"]:
                return self._send(200, {key: value for key, value in job.items() if key != "started"} | {"seconds": int(time.time() - job.get("started", time.time()))})
            if method == "POST" and parts == ["users"]:
                return self._send(200, create_user(json.loads(body or b"{}")))
            if len(parts) >= 2 and parts[0] == "users":
                user = parts[1]
                rest = parts[2:]
                if method == "GET" and not rest:
                    return self._send(200, user_view(user))
                if method == "POST" and not rest:
                    return self._send(200, update_user(user, json.loads(body or b"{}")))
                if method == "POST" and rest == ["photo"]:
                    slot = query.get("slot")
                    if slot not in ("front", "back") or not body:
                        raise ValueError("Send a front or back photo.")
                    photos = _user_dir(user) / "photos"
                    photos.mkdir(parents=True, exist_ok=True)
                    (photos / slot).write_bytes(body)
                    return self._send(200, {"saved": slot})
                if method == "POST" and rest == ["build"]:
                    return self._send(200, start_build(user, query.get("kind", ""), query.get("mirror") == "1"))
                if method == "POST" and rest == ["outfits"]:
                    return self._send(200, save_draft(user, json.loads(body or b"{}").get("name", "")))
                if method == "DELETE" and len(rest) == 2 and rest[0] == "outfits":
                    return self._send(200, delete_outfit(user, rest[1]))
            raise LookupError
        except LookupError:
            self._send(404, {"error": "Not found."})
        except ValueError as exc:
            self._send(400, {"error": str(exc)})

    def do_GET(self) -> None:  # noqa: N802
        if urlparse(self.path).path in ("", "/"):
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:8092/studio/")
            self.end_headers()
            return
        self._route("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._route("POST")

    def do_DELETE(self) -> None:  # noqa: N802
        self._route("DELETE")

    def log_message(self, fmt: str, *args) -> None:
        pass


def main() -> None:
    print(f"DressMe studio API on http://127.0.0.1:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
