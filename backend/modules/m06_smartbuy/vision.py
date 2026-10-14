"""Real photo analysis with FashionCLIP (zero-shot): type + colour + 512-d image embedding.

This is a local stand-in for M1 /classify until BO3 ships it. Same output shape.
Install once:  pip install torch transformers pillow
First call downloads the model (~600 MB) from Hugging Face: patrickjohncyh/fashion-clip
"""

import io
from functools import lru_cache

from . import synthetic as syn

MODEL = "patrickjohncyh/fashion-clip"

TYPE_PROMPTS = {
    "shirt": "a button-up shirt", "t-shirt": "a t-shirt", "sweater": "a knit sweater", "blouse": "a women's blouse",
    "jeans": "a pair of jeans", "chinos": "a pair of chino trousers", "trousers": "a pair of tailored trousers",
    "skirt": "a skirt", "sneakers": "a pair of sneakers", "loafers": "a pair of loafers", "boots": "a pair of boots",
    "sandals": "a pair of sandals", "jacket": "a casual jacket", "coat": "a long coat", "blazer": "a blazer",
    "dress": "a dress", "jebba": "a traditional Tunisian jebba robe",
}


class VisionUnavailable(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _load():
    try:
        import torch
        from transformers import CLIPModel, CLIPProcessor
    except ImportError as e:
        raise VisionUnavailable("Install the vision model first:  pip install torch transformers pillow") from e
    model = CLIPModel.from_pretrained(MODEL).eval()
    proc = CLIPProcessor.from_pretrained(MODEL)
    with torch.no_grad():
        def text_emb(texts):
            t = proc(text=texts, return_tensors="pt", padding=True)
            e = _text_features(model, t)
            return e / e.norm(dim=-1, keepdim=True)
        types = list(TYPE_PROMPTS)
        t_type = text_emb([f"a photo of {TYPE_PROMPTS[k]}" for k in types])
        colours = list(syn.COLOURS)
        t_col = text_emb([f"a photo of a {c} piece of clothing" for c in colours])
    return torch, model, proc, types, t_type, colours, t_col


def _image_features(model, inputs):
    """Projected image embedding. Built from the model parts so it works with old AND new
    transformers versions (newer ones return an output object from get_image_features)."""
    out = model.vision_model(pixel_values=inputs["pixel_values"])
    return model.visual_projection(out.pooler_output)


def _text_features(model, inputs):
    out = model.text_model(input_ids=inputs["input_ids"], attention_mask=inputs.get("attention_mask"))
    return model.text_projection(out.pooler_output)


def _probs(torch, img_emb, txt_emb, labels, k=3):
    logits = 100.0 * img_emb @ txt_emb.T
    p = logits.softmax(dim=-1)[0]
    top = torch.topk(p, k)
    return [(labels[i], round(float(s), 3)) for s, i in zip(top.values, top.indices)]


def pixel_colour(img) -> tuple[str, float]:
    """Colour from the pixels: drop the background (colour of the border), take the median of the
    garment pixels, return the nearest named colour. Good at dark shades (black vs navy) where CLIP hesitates."""
    import numpy as np

    small = np.asarray(img.convert("RGB").resize((96, 96)), dtype=float)
    border = np.concatenate([small[0], small[-1], small[:, 0], small[:, -1]])
    bg = np.median(border, axis=0)
    px = small.reshape(-1, 3)
    garment = px[np.linalg.norm(px - bg, axis=1) > 40]
    if len(garment) < 200:  # no clear background: use the centre
        garment = small[24:72, 24:72].reshape(-1, 3)
    rgb = np.median(garment, axis=0)
    names = list(syn.COLOURS)
    ref = np.array([[int(syn.COLOURS[c][0][i:i + 2], 16) for i in (1, 3, 5)] for c in names], dtype=float)
    d = np.linalg.norm(ref - rgb, axis=1)
    i = int(d.argmin())
    conf = float(1 - d[i] / (np.sort(d)[1] + 1e-9))  # how much closer than the 2nd colour
    return names[i], round(max(conf, 0.0), 3)


def analyze(image_bytes: bytes) -> dict:
    """-> {subcategory, colour, category, confidence, alternatives, clip_embedding}"""
    from PIL import Image

    torch, model, proc, types, t_type, colours, t_col = _load()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    w, h = img.size
    centre = img.crop((w * 0.2, h * 0.2, w * 0.8, h * 0.8))  # colour: look at the garment, not the background
    with torch.no_grad():
        e = _image_features(model, proc(images=img, return_tensors="pt"))
        e = e / e.norm(dim=-1, keepdim=True)
        ec = _image_features(model, proc(images=centre, return_tensors="pt"))
        ec = ec / ec.norm(dim=-1, keepdim=True)
    t = _probs(torch, e, t_type, types)
    c = _probs(torch, ec, t_col, colours)
    sub, col = t[0][0], c[0][0]
    pcol, pconf = pixel_colour(img)
    if c[0][1] < 0.6 and pcol != col:  # CLIP unsure -> trust the pixels
        col, c = pcol, [(pcol, max(pconf, c[0][1]))] + [x for x in c if x[0] != pcol][:2]
    if col not in syn.TYPE_COLOURS[sub] and col != pcol:  # keep colours realistic for the type when the model hesitates
        for alt, _ in c[1:]:
            if alt in syn.TYPE_COLOURS[sub]:
                col = alt
                break
    return {
        "subcategory": sub, "colour": col, "category": syn.TYPES[sub][0],
        "confidence": {"type": t[0][1], "colour": c[0][1]},
        "alternatives": {"type": t, "colour": c},
        "clip_embedding": [round(float(x), 5) for x in e[0]],
    }
