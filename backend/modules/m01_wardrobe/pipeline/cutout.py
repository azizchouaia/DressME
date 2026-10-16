"""Background removal with rembg (isnet-general-use, fallback u2net). Session loaded once, lazily."""

import logging
import threading

import numpy as np

from ..config import get_config

log = logging.getLogger(__name__)

_session = None
_lock = threading.Lock()


def _get_session():
    global _session
    if _session is None:
        with _lock:
            if _session is None:
                from rembg import new_session

                models = get_config().models
                try:
                    _session = new_session(models.rembg)
                except Exception:  # model download / onnx error -> fallback
                    log.warning("rembg %s unavailable, using %s", models.rembg, models.rembg_fallback)
                    _session = new_session(models.rembg_fallback)
    return _session


def remove_background(img):
    """PIL image -> RGBA cutout, cropped to the garment. The alpha channel is the garment mask."""
    from rembg import remove

    out = remove(img.convert("RGB"), session=_get_session()).convert("RGBA")
    if (np.asarray(out.getchannel("A")) > 127).mean() < 0.01:   # nothing found: keep the full frame
        out = img.convert("RGBA")
        out.putalpha(255)
        return out
    return crop_to_mask(out)


def crop_to_mask(rgba, margin: float = 0.03):
    """Crop to the bounding box of the opaque pixels, plus a small transparent margin."""
    bbox = rgba.getchannel("A").point(lambda a: 255 if a > 127 else 0).getbbox()
    if bbox is None:
        return rgba
    left, top, right, bottom = bbox
    pad = int(margin * max(right - left, bottom - top))
    return rgba.crop((max(0, left - pad), max(0, top - pad),
                      min(rgba.width, right + pad), min(rgba.height, bottom + pad)))


def on_white(rgba):
    """Composite a cutout on a white background (what FashionCLIP saw in training)."""
    from PIL import Image

    bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    return Image.alpha_composite(bg, rgba.convert("RGBA")).convert("RGB")
