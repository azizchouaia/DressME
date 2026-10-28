"""Local TripoSR service.

Loads the MIT model once on this machine and turns one photo into a GLB.
The wardrobe backend calls http://127.0.0.1:8766 — the phone and the browser
never load the weights.

Run it with the virtualenv inside the TripoSR checkout:

    ai\\vendor\\TripoSR\\.venv\\Scripts\\python.exe ai\\triposr_server.py
"""

from __future__ import annotations

import io
import json
import logging
import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

REPO_ROOT = Path(__file__).resolve().parents[1]
TRIPOSR_ROOT = REPO_ROOT / "ai" / "vendor" / "TripoSR"
SHIM_ROOT = REPO_ROOT / "ai" / "shims"
HOST = "127.0.0.1"
PORT = int(os.environ.get("TRIPOSR_PORT", "8766"))
MC_RESOLUTION = int(os.environ.get("TRIPOSR_MC_RESOLUTION", "256"))
MAX_IMAGE_BYTES = 20 * 1024 * 1024

sys.path.insert(0, str(SHIM_ROOT))
sys.path.insert(0, str(TRIPOSR_ROOT))
sys.path.insert(0, str(REPO_ROOT / "ai"))

import numpy as np
import rembg
import torch
from PIL import Image

_torch_load = torch.load


def _load_checkpoint(*args, **kwargs):
    kwargs["weights_only"] = False
    return _torch_load(*args, **kwargs)


torch.load = _load_checkpoint

from prepare_body import prepare_body
from smplx_export import export_body
from tsr.system import TSR
from tsr.utils import remove_background, resize_foreground

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(message)s",
    level=logging.INFO,
)
log = logging.getLogger("triposr")

infer_lock = threading.Lock()
users_lock = threading.Lock()
USERS_DIR = REPO_ROOT / "avatar_studio" / "web" / "users"
model: TSR | None = None
rembg_session = None
clip_model = None
clip_processor = None
device = "cpu"

# Prompts match the wardrobe categories. The last one keeps chairs and other objects out of a slot.
GARMENT_PROMPTS: list[tuple[str, str]] = [
    ("t-shirt", "a photo of a t-shirt"),
    ("shirt", "a photo of a button-up shirt"),
    ("pants", "a photo of pants or shorts"),
    ("jeans", "a photo of jeans"),
    ("jacket", "a photo of a jacket or coat"),
    ("dress", "a photo of a dress"),
    ("shoes", "a photo of shoes"),
    ("other", "a photo of furniture or an object that is not clothing"),
]


def load_model() -> None:
    global model, rembg_session, device
    device = "cuda:0" if torch.cuda.is_available() else "cpu"
    log.info("Loading TripoSR on %s", device)
    loaded = TSR.from_pretrained(
        "stabilityai/TripoSR",
        config_name="config.yaml",
        weight_name="model.ckpt",
    )
    loaded.renderer.set_chunk_size(8192)
    loaded.to(device)
    model = loaded
    log.info("Loading background-removal model")
    rembg_session = rembg.new_session()
    _load_clip()
    log.info("TripoSR is ready")


def _load_clip() -> None:
    """Zero-shot clothing type. Failure here must not block 3D reconstruction."""
    global clip_model, clip_processor
    try:
        from transformers import CLIPModel, CLIPProcessor

        log.info("Loading clothing classifier on %s", device)
        clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
        loaded = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
        clip_device = device
        try:
            loaded = loaded.to(clip_device)
        except RuntimeError:
            log.warning("Classifier did not fit on %s; using CPU", device)
            clip_device = "cpu"
            loaded = loaded.to(clip_device)
        loaded.eval()
        clip_model = loaded
        log.info("Clothing classifier is ready on %s", clip_device)
    except Exception:
        log.exception("Clothing classifier failed to load; photos will keep their current category")


def classify(image_bytes: bytes) -> dict[str, object]:
    if clip_model is None or clip_processor is None:
        raise RuntimeError("Clothing classifier is not loaded.")
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    texts = [prompt for _, prompt in GARMENT_PROMPTS]
    inputs = clip_processor(text=texts, images=image, return_tensors="pt", padding=True)
    clip_device = next(clip_model.parameters()).device
    inputs = {key: value.to(clip_device) for key, value in inputs.items()}
    with infer_lock:
        with torch.no_grad():
            logits = clip_model(**inputs).logits_per_image.softmax(dim=-1)[0]
    index = int(logits.argmax())
    category, _prompt = GARMENT_PROMPTS[index]
    return {"category": category, "confidence": round(float(logits[index]), 4)}


def reconstruct(image_bytes: bytes, resolution: int | None = None) -> bytes:
    if model is None or rembg_session is None:
        raise RuntimeError("TripoSR is not loaded.")
    image = remove_background(Image.open(io.BytesIO(image_bytes)).convert("RGB"), rembg_session)
    image = resize_foreground(image, 0.85)
    array = np.array(image).astype(np.float32) / 255.0
    array = array[:, :, :3] * array[:, :, 3:4] + (1 - array[:, :, 3:4]) * 0.5
    prepared = Image.fromarray((array * 255.0).astype(np.uint8))

    with infer_lock:
        with torch.no_grad():
            scene_codes = model([prepared], device=device)
        meshes = model.extract_mesh(scene_codes, True, resolution=resolution or MC_RESOLUTION)

    log.info("Scan finished. Smoothing the mesh and standing it on its feet.")
    body = prepare_body(meshes[0])
    log.info("Body is ready: %s faces", len(body.faces))
    buffer = io.BytesIO()
    body.export(buffer, file_type="glb")
    return buffer.getvalue()


def _slug(name: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return (text or "person")[:40]


def list_avatars() -> list[dict[str, str]]:
    index = USERS_DIR / "index.json"
    if not index.is_file():
        return []
    try:
        data = json.loads(index.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    people = []
    for item in data:
        if isinstance(item, dict) and item.get("name") and item.get("url"):
            people.append({"name": str(item["name"]), "url": str(item["url"]), "gender": str(item.get("gender") or "neutral")})
    return people


def store_avatar(name: str, gender: str, glb: bytes) -> dict[str, str]:
    USERS_DIR.mkdir(parents=True, exist_ok=True)
    slug = _slug(name)
    path = USERS_DIR / f"{slug}.glb"
    url = f"/users/{path.name}"
    path.write_bytes(glb)
    with users_lock:
        people = [item for item in list_avatars() if item["url"] != url]
        people.append({"name": name.strip() or "Person", "url": url, "gender": gender})
        (USERS_DIR / "index.json").write_text(json.dumps(people), encoding="utf-8")
    return {"name": name.strip() or "Person", "url": url, "gender": gender}


def detect_gender(image_bytes: bytes) -> str:
    if clip_model is None or clip_processor is None:
        return "neutral"
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    prompts = [("female", "a full body photo of a woman"), ("male", "a full body photo of a man")]
    inputs = clip_processor(text=[text for _, text in prompts], images=image, return_tensors="pt", padding=True)
    clip_device = next(clip_model.parameters()).device
    inputs = {key: value.to(clip_device) for key, value in inputs.items()}
    with infer_lock:
        with torch.no_grad():
            scores = clip_model(**inputs).logits_per_image.softmax(dim=-1)[0]
    best = int(scores.argmax())
    gender = prompts[best][0]
    confidence = float(scores[best])
    log.info("Detected %s (%.2f)", gender, confidence)
    if confidence < 0.58:
        return "neutral"
    return gender


def detect_view(image_bytes: bytes) -> str:
    if clip_model is None or clip_processor is None:
        return "front"
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    prompts = [
        ("front", "a front view photo of a person facing the camera"),
        ("back", "a back view photo of a person facing away from the camera"),
        ("side", "a side profile photo of a person turned sideways"),
        ("three-quarter", "a three-quarter view photo of a person turned partly sideways"),
    ]
    inputs = clip_processor(text=[text for _, text in prompts], images=image, return_tensors="pt", padding=True)
    clip_device = next(clip_model.parameters()).device
    inputs = {key: value.to(clip_device) for key, value in inputs.items()}
    with infer_lock:
        with torch.no_grad():
            scores = clip_model(**inputs).logits_per_image.softmax(dim=-1)[0]
    best = int(scores.argmax())
    view = prompts[best][0]
    log.info("Photo looks like a %s view (%.2f)", view, float(scores[best]))
    return view


def clear_photos(name: str) -> None:
    folder = USERS_DIR / "_incoming" / _slug(name)
    if folder.is_dir():
        for path in folder.iterdir():
            if path.is_file():
                path.unlink()


def sample_colors(image_bytes: bytes) -> tuple[str, str]:
    image = remove_background(Image.open(io.BytesIO(image_bytes)).convert("RGB"), rembg_session)
    array = np.asarray(image)
    if array.ndim != 3 or array.shape[2] < 4:
        return "b9aea3", "3a2a22"
    alpha = array[:, :, 3]
    rows_hit = np.where(alpha > 180)[0]
    if rows_hit.size < 50:
        return "b9aea3", "3a2a22"
    top, bottom = int(rows_hit.min()), int(rows_hit.max())
    height = max(bottom - top, 1)
    rows = np.arange(array.shape[0])[:, None]
    rgb = array[:, :, :3].astype(np.float32)

    def median_hex(mask) -> str | None:
        pixels = rgb[mask]
        if pixels.shape[0] < 20:
            return None
        median = np.median(pixels, axis=0)
        return "".join(f"{int(max(0, min(255, channel))):02x}" for channel in median)

    hair_mask = (alpha > 180) & (rows < top + 0.14 * height)
    face = (alpha > 180) & (rows > top + 0.16 * height) & (rows < top + 0.32 * height)
    red, green, blue = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    skin_like = face & (red > 70) & (red > green) & (green > blue * 0.7) & ((red - blue) > 10)
    return median_hex(skin_like) or median_hex(face) or "b9aea3", median_hex(hair_mask) or "3a2a22"


def _scan_vertices(image_bytes: bytes):
    import trimesh

    scan = reconstruct(image_bytes, 128)
    mesh = trimesh.load(io.BytesIO(scan), file_type="glb", force="mesh")
    return np.asarray(mesh.vertices)


def build_from_photos(name: str, photos: dict[str, bytes], gender: str) -> tuple[bytes, dict[str, str]]:
    from smplx_export import targets_from_labeled

    if not photos:
        raise RuntimeError("Add at least one photo.")
    labeled = []
    front_photo = None
    for key, image in photos.items():
        view = detect_view(image)
        log.info("%s classified as %s", key, view)
        if view == "front" and front_photo is None:
            front_photo = image
        labeled.append((view, _scan_vertices(image)))
    counts: dict[str, int] = {}
    for view, _vertices in labeled:
        counts[view] = counts.get(view, 0) + 1
    chosen = gender if gender in {"female", "male"} else detect_gender(front_photo or next(iter(photos.values())))
    log.info("Scanning %s photo(s) for %s: %s", len(photos), name, counts)
    targets = targets_from_labeled(labeled)
    fitted = USERS_DIR / f"{_slug(name)}.glb"
    log.info("Fitting an SMPL-X body for %s (%s).", name, chosen)
    export_body(fitted, fitted, chosen, targets)
    stored = store_avatar(name, chosen, fitted.read_bytes())
    skin, hair = sample_colors(front_photo or next(iter(photos.values())))
    stored["views"] = ",".join(f"{view}:{count}" for view, count in sorted(counts.items()))
    stored["skin"] = skin
    stored["hair"] = hair
    log.info("Avatar saved at %s", stored["url"])
    return fitted.read_bytes(), stored


def save_photo(name: str, slot: str, image_bytes: bytes) -> None:
    if re.fullmatch(r"[a-z0-9-]{1,40}", slot) is None:
        raise RuntimeError("That photo could not be stored.")
    folder = USERS_DIR / "_incoming" / _slug(name)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / slot).write_bytes(image_bytes)


def saved_photos(name: str) -> dict[str, bytes]:
    folder = USERS_DIR / "_incoming" / _slug(name)
    photos = {}
    if not folder.is_dir():
        return photos
    for path in sorted(folder.iterdir()):
        if path.is_file():
            photos[path.name] = path.read_bytes()
    return photos


def build_avatar(image_bytes: bytes, name: str, gender: str) -> tuple[bytes, dict[str, str]]:
    return build_from_photos(name, {"front": image_bytes}, gender)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        log.info("%s - %s", self.address_string(), fmt % args)

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-TripoSR-Resolution")
        self.send_header(
            "Access-Control-Expose-Headers",
            "X-Avatar-Url, X-Avatar-Gender, X-Avatar-Views, X-Avatar-Skin, X-Avatar-Hair",
        )
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def _send(self, status: int, body: bytes, content_type: str, extra: dict[str, str] | None = None) -> None:
        self.send_response(status)
        self._cors()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self._cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0]
        if path == "/avatars":
            self._send(200, json.dumps(list_avatars()).encode("utf-8"), "application/json")
            return
        if path != "/health":
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        ready = model is not None
        payload = f'{{"status":"{"ok" if ready else "loading"}","device":"{device}"}}'.encode()
        self._send(200 if ready else 503, payload, "application/json")

    def _read_image(self) -> bytes | None:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > MAX_IMAGE_BYTES:
            self._send(413, b"Image is missing or larger than 20 MB.", "text/plain; charset=utf-8")
            return None
        return self.rfile.read(length)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if path not in {"/reconstruct", "/classify", "/avatar", "/avatar-photo", "/avatar-build", "/avatar-clear"}:
            self._send(404, b"not found", "text/plain; charset=utf-8")
            return
        query = parse_qs(urlparse(self.path).query)
        name = (query.get("name") or ["Person"])[0].strip() or "Person"
        if path == "/avatar-clear":
            clear_photos(name)
            self._send(200, b'{"cleared":true}', "application/json")
            return
        if path == "/avatar-build":
            try:
                gender = (query.get("gender") or ["auto"])[0].strip().lower()
                glb, stored = build_from_photos(name, saved_photos(name), gender)
            except Exception as exc:
                log.exception("Request failed")
                self._send(500, str(exc).encode("utf-8"), "text/plain; charset=utf-8")
                return
            self._send(200, glb, "model/gltf-binary", {
                "X-Avatar-Url": stored["url"],
                "X-Avatar-Gender": stored["gender"],
                "X-Avatar-Views": stored.get("views", ""),
                "X-Avatar-Skin": stored.get("skin", "b9aea3"),
                "X-Avatar-Hair": stored.get("hair", "3a2a22"),
            })
            return
        image = self._read_image()
        if image is None:
            return
        try:
            if path == "/avatar-photo":
                slot = (query.get("slot") or ["front"])[0].strip().lower()
                save_photo(name, slot, image)
                self._send(200, json.dumps({"saved": slot}).encode("utf-8"), "application/json")
                return
            if path == "/avatar":
                gender = (query.get("gender") or ["auto"])[0].strip().lower()
                glb, stored = build_avatar(image, name, gender)
                self._send(
                    200,
                    glb,
                    "model/gltf-binary",
                    {
                        "X-Avatar-Url": stored["url"],
                        "X-Avatar-Gender": stored["gender"],
                        "X-Avatar-Skin": stored.get("skin", "b9aea3"),
                        "X-Avatar-Hair": stored.get("hair", "3a2a22"),
                    },
                )
                return
            if path == "/classify":
                body = json.dumps(classify(image)).encode("utf-8")
                self._send(200, body, "application/json")
                return
            raw = self.headers.get("X-TripoSR-Resolution", "")
            try:
                resolution = int(raw) if raw else MC_RESOLUTION
            except ValueError:
                resolution = MC_RESOLUTION
            resolution = max(64, min(resolution, 320))
            glb = reconstruct(image, resolution)
        except Exception as exc:
            log.exception("Request failed")
            self._send(500, str(exc).encode("utf-8"), "text/plain; charset=utf-8")
            return
        self._send(200, glb, "model/gltf-binary")


def main() -> None:
    if not TRIPOSR_ROOT.is_dir():
        raise SystemExit(f"TripoSR checkout not found at {TRIPOSR_ROOT}")
    load_model()
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    log.info("Listening on http://%s:%s", HOST, PORT)
    server.serve_forever()


if __name__ == "__main__":
    main()
