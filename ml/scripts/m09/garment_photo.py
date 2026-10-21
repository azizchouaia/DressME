"""Phone photo(s) of a garment -> texture atlas + info for the 3D template. No training.

Runs in the isolated env (ml/.venv, rembg + numpy 2):
    ml/.venv/Scripts/python ml/scripts/m09/garment_photo.py --front f.jpg [--back b.jpg] --kind top --out DIR

1. background removal: rembg, pretrained BiRefNet (birefnet-general-lite, ~8 s on CPU); IS-Net with
   --fast (1 s) but it can keep only a big print instead of the whole garment
2. keep the largest object, crop it
3. split the garment: body of the garment (columns covered at the hem) vs sleeves (outside them, upper part)
4. flatten: the photo's creases and uneven light are removed, the design (prints, stripes, text) is kept
   main colour = biggest colour cluster of the garment body (prints are usually smaller than the base fabric)
5. trousers / shorts with two separate legs in the photo: each leg is straightened along its own axis (legs
   spread in a V are fine) -> atlas "legs" (see _build_legs). Otherwise:
6. atlas 2048 x 1536: [front body | back body (mirrored: seen from behind)] + a row of 4 sleeve squares
   [front L | front R | back L | back R] (L / R = image left / right of the front view). No back photo ->
   back = main colour; no visible sleeve -> sleeve colour.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

SIDE, STRIP = 1024, 128


def load(path: str, max_side: int = 1024) -> Image.Image:
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    im.thumbnail((max_side, max_side))
    return im


def segment(im: Image.Image, session) -> np.ndarray:
    from rembg import remove
    from scipy import ndimage

    alpha = np.asarray(remove(im, session=session, only_mask=True)) > 128
    lab, n = ndimage.label(alpha)
    if n > 1:  # keep the garment, drop small blobs (hanger, background bits)
        sizes = ndimage.sum(alpha, lab, range(1, n + 1))
        alpha = lab == (1 + int(np.argmax(sizes)))
    return ndimage.binary_fill_holes(alpha)


def main_colour(pixels: np.ndarray, k: int = 3, iters: int = 12) -> np.ndarray:
    rng = np.random.default_rng(0)
    px = pixels[rng.choice(len(pixels), min(len(pixels), 20000), replace=False)].astype(float)
    c = px[rng.choice(len(px), k, replace=False)]
    for _ in range(iters):
        lab = np.argmin(((px[:, None] - c[None]) ** 2).sum(-1), 1)
        c = np.array([px[lab == j].mean(0) if (lab == j).any() else c[j] for j in range(k)])
    counts = np.bincount(lab, minlength=k)
    return c[int(np.argmax(counts))]


def analyse(im: Image.Image, mask: np.ndarray, kind: str) -> dict:
    ys, xs = np.nonzero(mask)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    m = mask[y0:y1 + 1, x0:x1 + 1]
    rgb = np.asarray(im)[y0:y1 + 1, x0:x1 + 1]
    h, w = m.shape
    if kind in ("top", "outerwear", "dress"):
        bottom = m[int(h * 0.8):]  # the hem: only the body of the garment is there
        cols = np.nonzero(bottom.mean(0) > 0.3)[0]
        bx0, bx1 = (cols.min(), cols.max()) if len(cols) else (0, w - 1)
        # top of the garment body = first row covering a third of its width (skips hangers and labels)
        rows = np.nonzero(m[:, bx0:bx1 + 1].mean(1) > 0.33)[0]
        by0 = rows.min() if len(rows) else 0
        body = np.zeros_like(m)
        body[by0:, bx0:bx1 + 1] = m[by0:, bx0:bx1 + 1]
        sleeves = m & ~body
        sleeves[int(h * 0.6):] = False
    else:  # bottoms: the whole garment is "body", from the first row covering a third of its width
        waist_w = None
        bx0, bx1 = 0, w - 1
        rows = np.nonzero(m.mean(1) > 0.33)[0]
        by0 = rows.min() if len(rows) else 0
        body = np.zeros_like(m)
        body[by0:] = m[by0:]
        sleeves = np.zeros_like(m)
        # waist width = garment width just under the waistband; length / waist tells mini / midi / long skirts
        band = m[by0 + max(1, (h - by0) // 25): by0 + max(2, (h - by0) // 12)]
        waist_w = float(np.median(band.sum(1))) if len(band) else float(w)
    # shrink the cut-outs a few pixels: the edge of the segmentation carries a light outline that would show as
    # lines on the 3D seams
    from scipy import ndimage

    er = max(2, int(min(h, w) * 0.006))
    body = ndimage.binary_erosion(body, iterations=er)
    sleeves = ndimage.binary_erosion(sleeves, iterations=er)
    base = main_colour(rgb[body]) if body.any() else np.array([128, 128, 128])
    sleeve = np.median(rgb[sleeves], 0) if sleeves.sum() > 200 else base
    crop = rgb[by0:, bx0:bx1 + 1].copy()
    crop[~body[by0:, bx0:bx1 + 1]] = base  # outside the garment = its own colour (no background bleeding)
    crop = np.asarray(flatten(Image.fromarray(crop.astype(np.uint8))))
    sleeve_crops = {}
    for side, cols in (("L", slice(0, bx0)), ("R", slice(bx1 + 1, w))):  # L / R = image left / right
        sm = np.zeros_like(m)
        sm[:, cols] = sleeves[:, cols]
        if sm.sum() < 150:
            continue
        ys2, xs2 = np.nonzero(sm)
        sc = rgb[ys2.min():ys2.max() + 1, xs2.min():xs2.max() + 1].copy()
        sc[~sm[ys2.min():ys2.max() + 1, xs2.min():xs2.max() + 1]] = sleeve if sleeves.sum() > 200 else base
        sleeve_crops[side] = flatten(Image.fromarray(sc.astype(np.uint8)))
    leg_parts = legs(m, rgb, base, by0, er) if kind == "bottom" else None
    length_to_waist = round((h - by0) / waist_w, 3) if kind not in ("top", "outerwear", "dress") and waist_w else None
    return {"crop": Image.fromarray(crop.astype(np.uint8)), "base": base, "sleeve": sleeve, "length_to_waist": length_to_waist,
            "sleeve_crops": sleeve_crops, "legs": leg_parts,
            "body_aspect": round((bx1 - bx0 + 1) / max(1, h - by0), 3), "coverage": round(float(m.mean()), 3)}


def flatten(img: Image.Image, strength: float = 1.0) -> Image.Image:
    """Remove the photo's own shading (creases of a garment lying on a bed, uneven light) but keep its design.
    The 3D model makes its own folds and light, so photographed creases would look like stains.
    - broad light: divide by a very blurred luminance (normalised to its median)
    - creases: deviations from a local median smaller than ~ the contrast of a print are reduced to 30 %;
      strong ones (stripes, text, print edges, > 45 levels) are kept as they are."""
    from scipy import ndimage

    a = np.asarray(img).astype(np.float32)
    h, w = a.shape[:2]
    lum = a.mean(-1)
    illum = ndimage.gaussian_filter(lum, sigma=max(4.0, 0.12 * min(h, w)))
    illum /= np.median(illum) or 1.0
    a = a / np.clip(illum, 0.5, 2.0)[..., None]
    size = max(5, int(0.035 * min(h, w)) | 1)
    bg = np.stack([ndimage.median_filter(a[..., c], size=size) for c in range(3)], -1)
    dev = a - bg
    mag = np.abs(dev).max(-1, keepdims=True)
    keep = np.clip((mag - 18) / (45 - 18), 0, 1)  # 0 = crease-like, 1 = design
    keep = 0.3 + 0.7 * keep
    out = bg + dev * (1 - strength + strength * keep)
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def _crotch_row(m: np.ndarray, top: int) -> int | None:
    """First row (from the top) of the region where the garment is two separate legs, or None (skirt, legs
    touching). A row counts as "two legs" when it has two runs wider than 3 % of the garment width."""
    h, w = m.shape
    min_run = max(3, int(w * 0.03))

    def runs(row):
        d = np.diff(np.concatenate([[0], row.astype(np.int8), [0]]))
        starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
        return int(((ends - starts) >= min_run).sum())

    two = np.array([runs(m[y]) >= 2 for y in range(h)])
    # the legs = the longest stretch of "two legs" rows (small gaps allowed: creases, a hole); a split cuff or
    # a stray fold near the hem makes short stretches that are ignored
    tol = max(2, int(h * 0.02))
    best, cur, last = (0, None), None, None
    for y in range(top, h):
        if not two[y]:
            continue
        if cur is None or y - last > tol:
            cur = y
        last = y
        if last - cur > best[0]:
            best = (last - cur, cur)
    length, crotch = best
    return crotch if crotch is not None and length > 0.2 * (h - top) else None


def _leg_strip(leg: np.ndarray, rgb: np.ndarray, base, n_along: int = 768, n_across: int = 256) -> Image.Image:
    """Straighten one leg of the photo along its own centre line, so a leg lying at an angle or bent at the knee
    becomes a vertical strip; each row spans the leg from its image-left edge to its image-right edge.
    Pass 1 follows the main axis (PCA) and records the middle of the leg at each step; pass 2 samples across
    the smoothed centre line, perpendicular to its local direction."""
    from scipy import ndimage

    ys, xs = np.nonzero(leg)
    pts = np.stack([xs, ys], 1).astype(float)
    mu = pts.mean(0)
    _, vecs = np.linalg.eigh(np.cov((pts - mu).T))
    d = vecs[:, -1]
    if d[1] < 0:  # along = downwards (hip -> hem)
        d = -d
    s = (pts - mu) @ d
    width = np.abs((pts - mu) @ np.array([d[1], -d[0]])).max() + 4
    t = np.linspace(-width * 1.5, width * 1.5, 600)
    legf = leg.astype(np.float32)

    def across(c, dirv):
        nrm = np.array([dirv[1], -dirv[0]])
        if nrm[0] < 0:  # across = towards image right
            nrm = -nrm
        line = c[None] + t[:, None] * nrm[None]
        idx = np.nonzero(ndimage.map_coordinates(legf, [line[:, 1], line[:, 0]], order=0) > 0.5)[0]
        if len(idx) < 2:
            return None
        splits = np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)
        run = min(splits, key=lambda r: abs(t[r].mean()))  # the run around the centre line
        return nrm, t[run[0]], t[run[-1]]

    steps = np.linspace(s.min(), s.max(), n_along)
    centres = []
    for si in steps:  # pass 1: middle of the leg at each step of the main axis
        c = mu + si * d
        r = across(c, d)
        centres.append(c if r is None else c + r[0] * (r[1] + r[2]) / 2)
    centres = np.array(centres)
    k = 41  # smooth the centre line
    pad = np.pad(centres, ((k // 2, k // 2), (0, 0)), mode="edge")
    centres = np.stack([np.convolve(pad[:, j], np.ones(k) / k, mode="valid") for j in range(2)], 1)
    dirs = np.gradient(centres, axis=0)
    out = np.zeros((n_along, n_across, 3), np.float32)
    prev = None
    for i, c in enumerate(centres):  # pass 2: across the leg, perpendicular to the centre line
        dv = dirs[i] / (np.linalg.norm(dirs[i]) or 1)
        r = across(c, dv)
        if r is None:
            if prev is not None:
                out[i] = prev
            continue
        nrm, e0, e1 = r
        q = c[None] + np.linspace(e0, e1, n_across)[:, None] * nrm[None]
        row = np.stack([ndimage.map_coordinates(rgb[..., ch].astype(np.float32), [q[:, 1], q[:, 0]], order=1)
                        for ch in range(3)], 1)
        out[i] = prev = row
    out[(out.sum(-1) == 0)] = base
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


def legs(m: np.ndarray, rgb: np.ndarray, base, top: int, er: int) -> dict | None:
    """Trousers / shorts: the upper part (waist -> crotch) and each leg straightened on its own, or None."""
    from scipy import ndimage

    crotch = _crotch_row(m, top)
    if crotch is None:
        return None
    lower = ndimage.binary_erosion(m, iterations=er)
    lower[:crotch] = False
    lab, n = ndimage.label(lower)
    if n < 2:
        return None
    sizes = ndimage.sum(lower, lab, range(1, n + 1))
    two = [1 + int(i) for i in np.argsort(sizes)[-2:]]
    if sizes[two[0] - 1] < 0.25 * sizes[two[1] - 1]:  # not two real legs
        return None
    comps = sorted(two, key=lambda k: np.nonzero(lab == k)[1].mean())  # image left, image right
    strips = {side: flatten(_leg_strip(lab == k, rgb, base)) for side, k in zip(("L", "R"), comps)}
    up = ndimage.binary_erosion(m, iterations=er)
    up[crotch + max(2, (m.shape[0] - top) // 40):] = False
    up[:top] = False
    ys, xs = np.nonzero(up)
    if not len(ys):
        return None
    crop = rgb[ys.min():ys.max() + 1, xs.min():xs.max() + 1].copy()
    crop[~up[ys.min():ys.max() + 1, xs.min():xs.max() + 1]] = base
    upper = flatten(Image.fromarray(crop.astype(np.uint8)))
    # the parts are cleaned separately, so their brightness can differ: on the 3D model that shows as a band
    # across the thighs where the top of the trousers meets the legs. Match each leg to the upper part.
    ua = np.asarray(upper).astype(np.float32)
    ref = np.median(ua[int(len(ua) * 0.6):].reshape(-1, 3), 0)  # lower part of the waist -> crotch crop
    for side, st in strips.items():
        sa = np.asarray(st).astype(np.float32)
        top = np.median(sa[: max(4, len(sa) // 6)].reshape(-1, 3), 0)
        gain = np.clip(ref / np.maximum(top, 1.0), 0.75, 1.35)
        strips[side] = Image.fromarray(np.clip(sa * gain, 0, 255).astype(np.uint8))
    return {"upper": upper, "legs": strips}


def save_cutout(im: Image.Image, mask: np.ndarray, path: Path) -> None:
    """The piece alone on a transparent background (thumbnail of the wardrobe, input of FashionCLIP)."""
    ys, xs = np.nonzero(mask)
    rgba = np.dstack([np.asarray(im), (mask * 255).astype(np.uint8)])[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    cut = Image.fromarray(rgba, "RGBA")
    cut.thumbnail((640, 640))
    cut.save(path)


def hexcol(c) -> str:
    return "#{:02x}{:02x}{:02x}".format(*[int(round(float(v))) for v in c])


def build(front: str, back: str | None, kind: str, out: Path, fast: bool = False, ptype: str = "",
          length: str | None = None) -> dict:
    from rembg import new_session

    session = new_session("isnet-general-use" if fast else "birefnet-general-lite")
    out.mkdir(parents=True, exist_ok=True)
    f_im = load(front)
    f_mask = segment(f_im, session)
    f = analyse(f_im, f_mask, kind)
    save_cutout(f_im, f_mask, out / "cutout.png")
    b_im = b_mask = None
    if back:
        b_im = ImageOps.mirror(load(back))
        b_mask = segment(b_im, session)
    pattern_info = None
    if kind != "shoes":  # sewing pattern (2 panels) + its texture, for the cloth simulation
        import garment_pattern

        try:
            pattern_info = garment_pattern.write(out, kind, ptype or kind, f_im, f_mask, b_im, b_mask,
                                                 length=length, base_rgb=f["base"])
        except Exception as e:  # noqa: BLE001
            pattern_info = {"error": f"{type(e).__name__}: {e}"}
    b = None
    if back:
        # seen from behind: mirror first, so left / right match the front view (as on the 3D model)
        b = analyse(b_im, b_mask, kind)
    if f["legs"]:  # trousers / shorts: own layout
        res = _build_legs(f, b, f_im, kind, out, back)
        res["pattern"] = pattern_info
        json.dump(res, open(out / "info.json", "w"), indent=1)
        return res
    # atlas v2, 2048 x 1536: [front body | back body] on top, [front L | front R | back L | back R sleeves] below
    atlas = Image.new("RGB", (2 * SIDE, SIDE + SIDE // 2), tuple(int(v) for v in f["base"]))
    atlas.paste(f["crop"].resize((SIDE, SIDE), Image.LANCZOS), (0, 0))
    if b:
        atlas.paste(b["crop"].resize((SIDE, SIDE), Image.LANCZOS), (SIDE, 0))
    half = SIDE // 2
    if b:
        # a back photo lying at an angle can make the collar or a fold look like a sleeve: keep a back sleeve only
        # when its colour matches the front sleeve, else reuse the front sleeve (sleeves rarely differ front/back)
        for side in ("L", "R"):
            fc, bc = f["sleeve_crops"].get(side), b["sleeve_crops"].get(side)
            if bc is not None and fc is not None:
                d = np.abs(np.median(np.asarray(fc).reshape(-1, 3), 0) - np.median(np.asarray(bc).reshape(-1, 3), 0))
                if d.max() > 35:
                    b["sleeve_crops"][side] = fc
            elif bc is None and fc is not None:
                b["sleeve_crops"][side] = fc
    for k, (src, side) in enumerate([(f, "L"), (f, "R"), (b, "L"), (b, "R")]):
        box = (k * half, SIDE, (k + 1) * half, SIDE + half)
        if src and side in src["sleeve_crops"]:
            atlas.paste(src["sleeve_crops"][side].resize((half, half), Image.LANCZOS), box[:2])
        else:  # no sleeve photo: the sleeve colour (front) or the main colour (no back photo)
            col = (src or f)["sleeve"] if src else f["base"]
            atlas.paste(tuple(int(v) for v in col), box)
    atlas.save(out / "atlas.png")
    f_im.save(out / "front_input.jpg")
    info = {"kind": kind, "main_color": hexcol(f["base"]), "sleeve_color": hexcol(f["sleeve"]),
            "has_back_photo": bool(back), "front_body_aspect": f["body_aspect"], "length_to_waist": f["length_to_waist"],
            "sleeve_photos": {"front": sorted(f["sleeve_crops"]), "back": sorted(b["sleeve_crops"]) if b else []},
            "atlas": str((out / "atlas.png").resolve()), "layout": "v2", "pattern": pattern_info}
    json.dump(info, open(out / "info.json", "w"), indent=1)
    return info


def _build_legs(f: dict, b: dict | None, f_im, kind: str, out: Path, back) -> dict:
    """Atlas "legs", 2048 x 2048: [front upper | back upper] (waist -> crotch) in the top 512 px, then four
    512 x 1536 straightened legs [front L | front R | back L | back R] (hip at the top). No back photo (or no
    legs found on it) -> front legs mirrored for the back, upper back = main colour."""
    base = tuple(int(v) for v in f["base"])
    atlas = Image.new("RGB", (2 * SIDE, 2 * SIDE), base)
    atlas.paste(f["legs"]["upper"].resize((SIDE, SIDE // 2), Image.LANCZOS), (0, 0))
    bl = b["legs"] if b and b.get("legs") else None
    if bl:
        atlas.paste(bl["upper"].resize((SIDE, SIDE // 2), Image.LANCZOS), (SIDE, 0))
    q = SIDE // 2
    for k, (src, side) in enumerate([(f["legs"], "L"), (f["legs"], "R"), (bl, "L"), (bl, "R")]):
        strip = (src or f["legs"])["legs"][side]
        if src is None:
            strip = ImageOps.mirror(strip)
        atlas.paste(strip.resize((q, 3 * q), Image.LANCZOS), (k * q, q))
    atlas.save(out / "atlas.png")
    f_im.save(out / "front_input.jpg")
    info = {"kind": kind, "main_color": hexcol(f["base"]), "sleeve_color": hexcol(f["base"]),
            "has_back_photo": bool(back), "front_body_aspect": f["body_aspect"], "length_to_waist": f["length_to_waist"],
            "leg_photos": {"front": True, "back": bool(bl)}, "sleeve_photos": {"front": [], "back": []},
            "atlas": str((out / "atlas.png").resolve()), "layout": "legs"}
    json.dump(info, open(out / "info.json", "w"), indent=1)
    return info


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--front")
    ap.add_argument("--back")
    ap.add_argument("--kind", default="top")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--type", default="")
    ap.add_argument("--length")
    ap.add_argument("--colour")  # no photo: default pattern of the type in this colour
    a = ap.parse_args()
    if a.colour:
        import garment_pattern

        Path(a.out).mkdir(parents=True, exist_ok=True)
        print(json.dumps(garment_pattern.write(Path(a.out), a.kind, a.type or a.kind, colour=a.colour,
                                               length=a.length), indent=1))
    else:
        print(json.dumps(build(a.front, a.back, a.kind, Path(a.out), a.fast, a.type, a.length), indent=1))
