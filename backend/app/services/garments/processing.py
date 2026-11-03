"""Photo → 3D.

`unavailable` is the default and does not invent a mesh.
`triposr` sends the item photo to the local TripoSR service and stores the GLB.
That mesh is a reconstruction of the photographed object. It is not fitted onto
the avatar; Avatar Studio only wears the template garments under `/models/`.
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from app.core.config import REPO_ROOT, get_settings
from app.models.clothing_item import ClothingItem
from app.services.garments.categories import category_from_classification, ready_message
from app.services.storage import get_storage

logger = logging.getLogger("smart_wardrobe.triposr")

_start_lock = threading.Lock()


@dataclass
class ProcessingResult:
    status: str
    message: str
    glb_url: str | None = None
    category: str | None = None


class Garment3DProcessor(ABC):
    @abstractmethod
    def submit(self, item: ClothingItem) -> ProcessingResult: ...


class UnavailableGarmentProcessor(Garment3DProcessor):
    def submit(self, item: ClothingItem) -> ProcessingResult:
        if item.glb_url:
            return ProcessingResult(status="ready", message="This item already has a 3D model.")
        return ProcessingResult(
            status=item.status,
            message="Automatic 3D garment creation is not available yet.",
        )


class TripoSRError(RuntimeError):
    pass


def _python_executable() -> Path:
    return REPO_ROOT / "ai" / "vendor" / "TripoSR" / ".venv" / "Scripts" / "python.exe"


def _server_healthy(timeout: float = 2.0) -> bool:
    url = f"{get_settings().triposr_url.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def ensure_triposr_server() -> None:
    """Start the local model process if it is not already answering."""
    if _server_healthy():
        return
    python = _python_executable()
    if not python.is_file():
        raise TripoSRError(
            "TripoSR is not installed on this machine. "
            f"Expected the local environment at {python}."
        )
    script = REPO_ROOT / "ai" / "triposr_server.py"
    log_path = REPO_ROOT / "ai" / "vendor" / "triposr-server.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with _start_lock:
        if _server_healthy():
            return
        log_file = log_path.open("ab")
        subprocess.Popen(
            [str(python), str(script)],
            cwd=str(REPO_ROOT),
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        )
        deadline = time.time() + get_settings().triposr_timeout_seconds
        while time.time() < deadline:
            if _server_healthy():
                return
            time.sleep(1)
    raise TripoSRError(
        "TripoSR did not start. The first launch downloads the model weights. "
        f"See {log_path}."
    )


def classify_photo(image: bytes) -> str | None:
    """Ask the local model which garment this photo is. Never fails the 3D save."""
    request = urllib.request.Request(
        f"{get_settings().triposr_url.rstrip('/')}/classify",
        data=image,
        method="POST",
        headers={"Content-Type": "application/octet-stream"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
        logger.warning("Could not classify the photo: %s", exc)
        return None
    return category_from_classification(payload.get("category"), float(payload.get("confidence") or 0))


def reconstruct_photo(image: bytes, resolution: int | None = None) -> bytes:
    ensure_triposr_server()
    headers = {"Content-Type": "application/octet-stream"}
    if resolution is not None:
        headers["X-TripoSR-Resolution"] = str(resolution)
    request = urllib.request.Request(
        f"{get_settings().triposr_url.rstrip('/')}/reconstruct",
        data=image,
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(
            request, timeout=get_settings().triposr_timeout_seconds
        ) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise TripoSRError(detail or "TripoSR could not reconstruct this photo.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise TripoSRError("Lost the connection to the local TripoSR service.") from exc


class TripoSRProcessor(Garment3DProcessor):
    def submit(self, item: ClothingItem) -> ProcessingResult:
        if not item.image_key:
            return ProcessingResult(
                status=item.status,
                message="Add a photo of this piece before creating a 3D preview.",
            )
        try:
            image = get_storage().read(item.image_key)
            glb = reconstruct_photo(image)
            category = classify_photo(image)
        except TripoSRError as exc:
            logger.warning("TripoSR failed for %s: %s", item.id, exc)
            return ProcessingResult(status="failed", message=str(exc))
        except Exception:
            logger.exception("TripoSR failed for %s", item.id)
            return ProcessingResult(status="failed", message="Could not build a 3D preview from this photo.")
        key = f"models/{item.user_id}/{item.id}.glb"
        url = get_storage().save(key, glb, "model/gltf-binary")
        return ProcessingResult(
            status="ready",
            message=ready_message(category),
            glb_url=url,
            category=category,
        )


def get_garment_processor() -> Garment3DProcessor:
    settings = get_settings()
    if settings.environment == "test" or settings.garment_processor != "triposr":
        return UnavailableGarmentProcessor()
    return TripoSRProcessor()
