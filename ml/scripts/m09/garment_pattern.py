"""Flat-lay photo -> sewing pattern (2 panels) for the cloth simulation in Blender. No training.

How real garments are made (and how CLO3D / Marvelous Designer / GarmentCode simulate them): flat pattern
pieces are sewn together around the body. A garment photographed flat IS its pattern seen from the front: its
outline is the front panel, and the back panel has the same outline. So:

1. clean outline of the garment (hanger hooks and labels removed, edge smoothed)
2. triangulated panel mesh (Delaunay on a regular grid + the resampled outline): regular triangles for the solver
3. each outline point is either SEWN (front to back: shoulders, sides, under the sleeves, inseams, outseams) or an
   OPENING (neck, sleeve ends, hem, waist, leg ends, armholes of sleeveless garments)
4. landmarks used to place the panels on the avatar: panel width at the chest / hips (-> real size from the size
   chart), shoulder line or waistline height, sleeve and leg axes (to align them with the avatar's arms / legs)

The texture is the photo itself: every panel vertex keeps its pixel position as UV (front photo for the front
panel, back photo aligned on the same outline for the back panel), so prints sit exactly where they are on the
garment and follow every fold of the simulation.
"""

from __future__ import annotations

import numpy as np

SEWN, NECK, HEM, SLEEVE_END, WAIST, LEG_END, ARMHOLE = 0, 1, 2, 3, 4, 5, 6
OPEN_NAMES = {SEWN: "sewn", NECK: "neck", HEM: "hem", SLEEVE_END: "sleeve_end", WAIST: "waist", LEG_END: "leg_end",
              ARMHOLE: "armhole"}


# ---------------- outline ----------------
def clean_mask(mask: np.ndarray) -> np.ndarray:
    """Remove thin structures (hanger hook, strings, labels) and keep the garment."""
    from scipy import ndimage

    m = mask.astype(bool)
    r = max(2, int(0.012 * max(m.shape)))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    disk = xx * xx + yy * yy <= r * r
    opened = ndimage.binary_opening(m, structure=disk)
    lab, n = ndimage.label(opened)
    if n == 0:
        return m
    sizes = ndimage.sum(opened, lab, range(1, n + 1))
    keep = lab == (1 + int(np.argmax(sizes)))
    return ndimage.binary_fill_holes(keep)


def outline(mask: np.ndarray, spacing: float) -> np.ndarray:
    """Ordered outline (x, y), smoothed, resampled every `spacing` px, counter-clockwise on screen."""
    from skimage import measure

    pad = np.pad(mask.astype(float), 2)
    cs = measure.find_contours(pad, 0.5)
    c = max(cs, key=len)[:, ::-1] - 2.0  # (x, y)
    if np.allclose(c[0], c[-1]):
        c = c[:-1]
    k = max(3, int(len(c) * 0.006)) | 1  # light circular smoothing (jagged mask edge -> jagged hem)
    ker = np.ones(k) / k
    c = np.stack([np.convolve(np.r_[c[-k:, i], c[:, i], c[:k, i]], ker, "same")[k:-k] for i in range(2)], 1)
    seg = np.linalg.norm(np.diff(np.r_[c, c[:1]], axis=0), axis=1)
    s = np.r_[0, np.cumsum(seg)]
    n = max(24, int(s[-1] / spacing))
    t = np.linspace(0, s[-1], n, endpoint=False)
    closed = np.r_[c, c[:1]]
    pts = np.stack([np.interp(t, s, closed[:, 0]), np.interp(t, s, closed[:, 1])], 1)
    area = 0.5 * np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1])
    return pts if area > 0 else pts[::-1]


def outward_normals(pts: np.ndarray, mask: np.ndarray) -> np.ndarray:
    tang = np.roll(pts, -1, 0) - np.roll(pts, 1, 0)
    tang /= np.maximum(np.linalg.norm(tang, axis=1, keepdims=True), 1e-9)
    nrm = np.stack([tang[:, 1], -tang[:, 0]], 1)
    pad = 8  # the garment touches the crop's borders: a probe beyond them is outside, not "clipped inside"
    mp = np.pad(mask, pad)
    h, w = mp.shape
    probe = np.clip(np.round(pts + pad + 4 * nrm).astype(int), 0, [w - 1, h - 1])
    inside = mp[probe[:, 1], probe[:, 0]]
    nrm[inside] *= -1  # the probe must land outside the garment
    return nrm


def triangulate(boundary: np.ndarray, mask: np.ndarray, spacing: float) -> tuple[np.ndarray, np.ndarray]:
    """Panel mesh: outline points first (same order), then a regular grid inside. Returns (verts, tris)."""
    from scipy.spatial import Delaunay, cKDTree
    from skimage.measure import points_in_poly

    x0, y0 = boundary.min(0)
    x1, y1 = boundary.max(0)
    gx, gy = np.meshgrid(np.arange(x0, x1, spacing), np.arange(y0, y1, spacing * 0.866))
    gx = gx + (np.arange(gx.shape[0])[:, None] % 2) * spacing * 0.5  # hexagonal grid: well-shaped triangles
    grid = np.stack([gx.ravel(), gy.ravel()], 1)
    grid = grid[points_in_poly(grid, boundary)]
    d, _ = cKDTree(boundary).query(grid)
    grid = grid[d > 0.55 * spacing]
    verts = np.r_[boundary, grid]
    tri = Delaunay(verts).simplices
    cen = verts[tri].mean(1)
    ok = points_in_poly(cen, boundary)
    e = np.linalg.norm(verts[tri] - verts[np.roll(tri, 1, 1)], axis=2).max(1)
    tri = tri[ok & (e < 2.2 * spacing)]
    # consistent winding (counter-clockwise on screen = facing the camera)
    a, b, c = verts[tri[:, 0]], verts[tri[:, 1]], verts[tri[:, 2]]
    cross = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    tri[cross < 0] = tri[cross < 0][:, ::-1]
    return verts, tri


# ---------------- straighten + symmetrize ----------------
def tilt_deg(mask: np.ndarray, garment: str) -> float:
    """Angle (degrees, counter-clockwise) that makes the garment's centre line vertical: line fit through the
    middle of each row (torso rows for tops, waist / hips for trousers, the whole skirt)."""
    rows = np.nonzero(mask.any(1))[0]
    y0, y1 = rows.min(), rows.max()
    H = y1 - y0 + 1
    lo, hi = {"top": (0.45, 0.95), "dress": (0.15, 0.6), "skirt": (0.0, 0.9), "pants": (0.0, 0.25)}.get(garment,
                                                                                                    (0.3, 0.9))
    ys, mids = [], []
    for r in range(int(y0 + lo * H), int(y0 + hi * H)):
        row = mask[r]
        if row.any():
            left, right = row.argmax(), len(row) - 1 - row[::-1].argmax()
            ys.append(r)
            mids.append((left + right) / 2)
    if len(ys) < 10:
        return 0.0
    a = np.polyfit(ys, mids, 1)[0]
    ang = float(np.degrees(np.arctan(a)))
    return ang if abs(ang) < 20 else 0.0


def rotate_img(im, angle: float):
    """PIL image rotated counter-clockwise around its centre, canvas expanded (same transform for masks)."""
    from PIL import Image

    if abs(angle) < 0.3:
        return im
    resample = Image.NEAREST if im.mode in ("1", "L") else Image.BICUBIC
    return im.rotate(angle, resample=resample, expand=True)


def symmetrize_top(mask: np.ndarray, cx: float, half_torso: float) -> np.ndarray:
    """Tops: torso = what both sides share; sleeves = the better (bigger) sleeve, mirrored to the other side (a
    folded or crumpled sleeve on one side of the photo does not make the garment asymmetric)."""
    h, w = mask.shape
    xs = np.arange(w)
    src = np.round(2 * cx - xs).astype(int)
    ok = (src >= 0) & (src < w)
    mirrored = np.zeros_like(mask)
    mirrored[:, ok] = mask[:, src[ok]]
    out = mask & mirrored
    torso = np.abs(xs - cx) <= half_torso * 1.02
    left = (xs < cx) & ~torso
    right = (xs > cx) & ~torso
    if mask[:, left].sum() >= mask[:, right].sum():
        out[:, left] = mask[:, left]
        out[:, right] = mirrored[:, right]
    else:
        out[:, right] = mask[:, right]
        out[:, left] = mirrored[:, left]
    return out


def clip_hanging_sleeves(mask: np.ndarray) -> np.ndarray:
    """Dress on a hanger with its sleeves hanging down its sides: above the cuffs the silhouette's sides are
    sleeves, not the dress. Where the cuffs end the silhouette narrows abruptly; above that row the dress is
    clipped to the width it has just below it."""
    rows = np.nonzero(mask.any(1))[0]
    y0, y1 = rows.min(), rows.max()
    H = y1 - y0 + 1
    rr = list(range(int(y0 + 0.15 * H), int(y0 + 0.9 * H)))
    L = np.array([mask[r].argmax() if mask[r].any() else 0 for r in rr])
    R = np.array([mask.shape[1] - 1 - mask[r][::-1].argmax() if mask[r].any() else 0 for r in rr])
    w = np.convolve(R - L, np.ones(5) / 5, "same")
    lo, hi = int(0.2 * len(rr)), int(0.8 * len(rr))
    if hi - lo < 10:
        return mask
    win = max(4, int(0.1 * len(rr)))  # the cuffs end over a few centimetres
    drops = w[lo:hi - win] - w[lo + win:hi]
    k = lo + int(np.argmax(drops))
    if drops.max() < 0.12 * w.max():  # no cuffs ending on the sides: nothing to clip
        return mask
    k += win  # the row where the narrowing ends
    below = slice(k + 2, min(len(rr), k + 20))
    bw = float(np.median((R - L)[below]))
    cx = float(np.median(((R + L) / 2)[below]))
    out = mask.copy()
    cut = rr[min(k, len(rr) - 1)]
    half = 0.5 * bw * 1.03
    out[:cut, :max(0, int(cx - half))] = False
    out[:cut, int(cx + half) + 1:] = False
    return out


def symmetrize(mask: np.ndarray, cx: float) -> np.ndarray:
    """Keep what the garment has on both sides of its centre line (a one-sided crease or flare of the flat-lay
    photo is not part of the garment; real patterns are left / right symmetric)."""
    h, w = mask.shape
    xs = np.arange(w)
    src = np.round(2 * cx - xs).astype(int)
    ok = (src >= 0) & (src < w)
    mirrored = np.zeros_like(mask)
    mirrored[:, ok] = mask[:, src[ok]]
    return mask & mirrored


# ---------------- landmarks + openings ----------------
def _pca_axis(pts: np.ndarray, outward: np.ndarray) -> np.ndarray:
    mu = pts.mean(0)
    _, vecs = np.linalg.eigh(np.cov((pts - mu).T))
    d = vecs[:, -1]
    return d if d @ outward >= 0 else -d


def _top_profile(mask: np.ndarray) -> np.ndarray:
    h = mask.shape[0]
    any_ = mask.any(0)
    top = np.where(any_, mask.argmax(0), h)
    return top


def _bottom_profile(mask: np.ndarray) -> np.ndarray:
    h = mask.shape[0]
    any_ = mask.any(0)
    return np.where(any_, h - 1 - mask[::-1].argmax(0), -1)


def analyse_top(mask: np.ndarray, pts: np.ndarray, nrm: np.ndarray) -> dict:
    h, w = mask.shape
    rows = np.nonzero(mask.any(1))[0]
    y0, y1 = rows.min(), rows.max()
    H = y1 - y0 + 1
    # torso columns: rows of the lower half where the garment is narrowest (no sleeve there; a flared or tilted
    # hem must not count as the torso)
    cand = [r for r in range(int(y0 + 0.45 * H), int(y0 + 0.95 * H)) if mask[r].any()]
    lefts = np.array([mask[r].argmax() for r in cand])
    rights = np.array([w - 1 - mask[r][::-1].argmax() for r in cand])
    widths = rights - lefts
    body = widths <= widths.min() * 1.08 + 2
    bx0, bx1 = float(np.median(lefts[body])), float(np.median(rights[body]))
    cx, bw = (bx0 + bx1) / 2, bx1 - bx0
    top = _top_profile(mask)
    neck_half = 0.19 * bw
    xs = [int(np.clip(cx - neck_half, 0, w - 1)), int(np.clip(cx + neck_half, 0, w - 1))]
    shoulder_y = float(min(top[xs[0]], top[xs[1]]))
    # sleeves: garment outside the body columns, upper 65 %
    yy, xx = np.nonzero(mask)
    margin = 0.03 * bw
    sleeves = {}
    for side, sel in (("L", xx < bx0 - margin), ("R", xx > bx1 + margin)):
        sel = sel & (yy < y0 + 0.65 * H)
        if sel.sum() < 0.004 * mask.sum():
            continue
        sp = np.stack([xx[sel], yy[sel]], 1).astype(float)
        root_x = bx0 if side == "L" else bx1
        near = sp[np.abs(sp[:, 0] - root_x) < 0.06 * bw]
        root = np.array([root_x, near[:, 1].mean() if len(near) else sp[:, 1].min()])
        # direction = root -> far end (a short sleeve is wider than long: its main axis is useless)
        reach = np.abs(sp[:, 0] - root_x)
        end = sp[reach > 0.8 * reach.max()].mean(0)
        d = (end - root) / max(1e-6, np.linalg.norm(end - root))
        outward_x = -d[0] if side == "L" else d[0]
        if outward_x < 0.35 or reach.max() < 0.12 * bw:  # hangs along the body (dress on a hanger) or folded
            continue
        proj = (sp - root) @ d
        sleeves[side] = {"root": root.tolist(), "dir": d.tolist(), "end": end.tolist(),
                         "length": float(np.linalg.norm(end - root)), "cap": float(proj.max()),
                         "mu": root.tolist()}
    # armpit: lowest point of the sleeve / body junction on each side
    armpit = {}
    for side in ("L", "R"):
        root_x = bx0 if side == "L" else bx1
        if side not in sleeves:  # sleeveless (or folded sleeves): armhole about 30 % of the length deep
            armpit[side] = float(shoulder_y + 0.3 * H)
            continue
        start = int(sleeves[side]["root"][1])
        y_ap = None
        for r in range(start, int(y0 + 0.75 * H)):
            if not mask[r].any():
                continue
            edge = mask[r].argmax() if side == "L" else w - 1 - mask[r][::-1].argmax()
            if (side == "L" and edge >= root_x - 0.02 * bw) or (side == "R" and edge <= root_x + 0.02 * bw):
                y_ap = r
                break
        armpit[side] = float(y_ap if y_ap is not None else shoulder_y + 0.3 * H)
    # chest width just under the armpits (what the size chart's chest girth is about)
    ap = int(max(armpit.values()))
    rows_c = [r for r in range(ap + int(0.03 * H), min(h, ap + int(0.12 * H))) if mask[r].any()]
    if rows_c:
        lc = np.array([mask[r].argmax() for r in rows_c])
        rc = np.array([w - 1 - mask[r][::-1].argmax() for r in rows_c])
        chest_w = float(np.median(rc - lc))
    else:
        chest_w = bw
    # openings
    bot = _bottom_profile(mask)
    kinds = np.full(len(pts), SEWN)
    for i, (p, n) in enumerate(zip(pts, nrm)):
        x, y = p
        xi = int(np.clip(round(x), 0, w - 1))
        if y < shoulder_y + 0.08 * H and abs(x - cx) < neck_half * 1.05 and n[1] < 0.3:
            kinds[i] = NECK
        elif y > bot[xi] - 0.03 * H and bx0 - 0.04 * bw <= x <= bx1 + 0.04 * bw and n[1] > 0.35 and \
                y > max(armpit.values()) + 0.1 * H:
            kinds[i] = HEM
        else:
            for side, s in sleeves.items():
                d = np.array(s["dir"])
                beyond = x < bx0 - 0.03 * bw if side == "L" else x > bx1 + 0.03 * bw  # on the sleeve, not the side
                beyond = beyond and y < armpit[side] + 0.12 * H  # not a flared hem corner
                if beyond and (p - np.array(s["mu"])) @ d > s["cap"] - 0.035 * H and n @ d > 0.3:
                    kinds[i] = SLEEVE_END
            if kinds[i] == SEWN:
                for side in ("L", "R"):
                    if side in sleeves:
                        continue
                    left = side == "L"
                    if (x < cx) == left and y < armpit[side] and abs(x - cx) > neck_half and abs(n[0]) > 0.45:
                        kinds[i] = ARMHOLE
    return {"cx": cx, "bw": bw, "width_px": min(chest_w, bw * 1.15), "anchor_y": shoulder_y, "y0": float(y0), "y1": float(y1),
            "neck_half": neck_half, "sleeves": sleeves, "armpit": armpit, "kinds": kinds}


def analyse_bottom(mask: np.ndarray, pts: np.ndarray, nrm: np.ndarray, skirt: bool) -> dict:
    import garment_photo as gp

    h, w = mask.shape
    rows = np.nonzero(mask.any(1))[0]
    y0, y1 = rows.min(), rows.max()
    H = y1 - y0 + 1
    top = _top_profile(mask)
    bot = _bottom_profile(mask)
    cols = np.nonzero(mask.any(0))[0]
    upper = [r for r in range(y0, int(y0 + 0.2 * H)) if mask[r].any()]
    widths = [mask[r].sum() for r in upper] or [len(cols)]
    width_px = float(np.max(widths))
    crotch = None if skirt else gp._crotch_row(mask, int(y0))
    legs = {}
    if crotch is not None:
        from scipy import ndimage

        lower = mask.copy()
        lower[:crotch] = False
        lab, n = ndimage.label(lower)
        if n >= 2:
            sizes = ndimage.sum(lower, lab, range(1, n + 1))
            ks = [1 + int(i) for i in np.argsort(sizes)[-2:]]
            for k in ks:
                ly, lx = np.nonzero(lab == k)
                lp = np.stack([lx, ly], 1).astype(float)
                side = "L" if lp[:, 0].mean() < (cols.min() + cols.max()) / 2 else "R"
                root = lp[lp[:, 1] < lp[:, 1].min() + 0.04 * H].mean(0)
                # direction = root -> far end (short wide legs of shorts: main axis is horizontal)
                dist = np.linalg.norm(lp - root, axis=1)
                end = lp[dist > 0.85 * dist.max()].mean(0)
                d = (end - root) / max(1e-6, np.linalg.norm(end - root))
                legs[side] = {"root": root.tolist(), "dir": d.tolist(), "mu": root.tolist(),
                              "cap": float(((lp - root) @ d).max()), "end": end.tolist()}
    cx = float((cols.min() + cols.max()) / 2) if crotch is None else float(np.mean([l_["root"][0] for l_ in legs.values()]) if legs else (cols.min() + cols.max()) / 2)
    kinds = np.full(len(pts), SEWN)
    for i, (p, n) in enumerate(zip(pts, nrm)):
        x, y = p
        xi = int(np.clip(round(x), 0, w - 1))
        if y < top[xi] + 0.03 * H and n[1] < -0.6 and y < y0 + 0.12 * H:
            kinds[i] = WAIST
        elif legs:
            for s in legs.values():
                d = np.array(s["dir"])
                if (p - np.array(s["mu"])) @ d > s["cap"] - 0.03 * H and n @ d > 0.3:
                    kinds[i] = LEG_END
        elif y > bot[xi] - 0.03 * H and n[1] > 0.35 and y > y0 + 0.5 * H:
            kinds[i] = HEM
    top_rows = [r for r in range(y0, int(y0 + 0.05 * H) + 1) if mask[r].any()]
    waist_w = float(np.median([mask[r].sum() for r in top_rows])) if top_rows else width_px
    return {"cx": cx, "width_px": width_px, "waist_px": waist_w, "anchor_y": float(y0), "y0": float(y0), "y1": float(y1),
            "crotch_y": None if crotch is None else float(crotch), "legs": legs, "kinds": kinds}


def prepare_mask(mask: np.ndarray, kind: str, ptype: str = "") -> tuple[np.ndarray, float, str]:
    """Cleaned, straightened mask (full image size after rotation) + the rotation applied + garment family."""
    from PIL import Image

    m = clean_mask(mask)
    skirt = ptype.lower().startswith("skirt")
    fam = "pants" if kind == "bottom" and not skirt else ("skirt" if kind == "bottom" else
                                                          ("dress" if kind == "dress" else "top"))
    ang = tilt_deg(m, fam) if fam != "pants" else 0.0  # legs at an angle are aligned later, not here
    if abs(ang) >= 0.3:
        m = np.asarray(rotate_img(Image.fromarray((m * 255).astype(np.uint8)), ang)) > 127
        m = clean_mask(m)
    return m, ang, fam


def build_pattern(mask: np.ndarray, kind: str, ptype: str = "") -> dict:
    """mask (full photo) -> pattern dict (pixel units of the garment's crop in the straightened photo)."""
    m, angle, fam = prepare_mask(mask, kind, ptype)
    if fam in ("top", "dress", "skirt"):  # left / right symmetric outline
        ys_, xs_ = np.nonzero(m)
        if fam == "top":
            rows = np.nonzero(m.any(1))[0]
            y0_, y1_ = rows.min(), rows.max()
            band = m[int(y0_ + 0.55 * (y1_ - y0_)):int(y0_ + 0.9 * (y1_ - y0_))]
            lefts = [r.argmax() for r in band if r.any()]
            rights = [len(r) - 1 - r[::-1].argmax() for r in band if r.any()]
            cx_ = (np.median(lefts) + np.median(rights)) / 2
        else:
            cx_ = (xs_.min() + xs_.max()) / 2
        if fam == "dress":
            m = clip_hanging_sleeves(m)
        if fam == "top":
            m = clean_mask(symmetrize_top(m, cx_, (np.median(rights) - np.median(lefts)) / 2))
        else:
            sym = symmetrize(m, cx_)
            if sym.sum() > 0.6 * m.sum():
                m = clean_mask(sym)
    ys, xs = np.nonzero(m)
    m = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    off = [int(xs.min()), int(ys.min())]
    spacing = max(m.shape) / 46.0
    pts = outline(m, spacing * 0.7)
    nrm = outward_normals(pts, m)
    skirt = ptype.lower().startswith("skirt")
    if kind in ("bottom",):
        info = analyse_bottom(m, pts, nrm, skirt)
        info["garment"] = "skirt" if skirt or not info["legs"] else "pants"
    else:
        info = analyse_top(m, pts, nrm)
        info["garment"] = "dress" if kind == "dress" else "top"
    verts, tris = triangulate(pts, m, spacing)
    kinds = info.pop("kinds")
    return {"version": 2, "kind": kind, "garment": info["garment"], "rotation_deg": angle,
            "size_px": [int(m.shape[1]), int(m.shape[0])],
            "offset_px": off, "spacing_px": spacing, "verts": np.round(verts, 2).tolist(),
            "tris": tris.astype(int).tolist(), "boundary": list(range(len(pts))), "open": kinds.astype(int).tolist(),
            "info": info, "mask_clean": m}



# ---------------- default patterns (pieces without a photo) ----------------
def default_mask(ptype: str, length: str | None = None) -> np.ndarray:
    """Clean silhouette of a garment type laid flat (proportions of real garments, ~1 px = 1 mm)."""
    from PIL import Image, ImageDraw

    t = (ptype or "t-shirt").lower()
    W, H = 1400, 1500
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    c = W // 2
    tops_long = {"long-sleeve top", "sweater", "hoodie", "shirt", "jacket", "blazer", "coat", "sweatshirt"}
    if t in ("pants", "jeans", "cargo pants", "joggers", "trousers", "shorts"):
        hem = 560 if t == "shorts" else 1080
        leg_w = 300 if t == "shorts" else 200
        d.polygon([(c - 230, 40), (c + 230, 40), (c + 255, 260), (c + 270, hem), (c + 270 - leg_w, hem),
                   (c + 10, 360), (c - 10, 360), (c - 270 + leg_w, hem), (c - 270, hem), (c - 255, 260)], fill=255)
    elif t.startswith("skirt"):
        L, B = {"mini": (430, 300), "midi": (720, 340), "long": (980, 380)}.get(length or "midi", (720, 340))
        d.polygon([(c - 200, 40), (c + 200, 40), (c + B, 40 + L), (c - B, 40 + L)], fill=255)
    elif t == "dress":
        d.polygon([(c - 95, 60), (c - 180, 60), (c - 185, 330), (c - 240, 600), (c - 330, 1100), (c + 330, 1100),
                   (c + 240, 600), (c + 185, 330), (c + 180, 60), (c + 95, 60), (c, 110)], fill=255)
    else:
        long_ = t in tops_long
        sl = [(c + 250, 200), (c + 640, 560), (c + 560, 640), (c + 250, 410)] if long_ else \
             [(c + 250, 190), (c + 430, 300), (c + 360, 430), (c + 250, 380)]
        body = [(c + 95, 120), (c + 250, 175)] + sl + [(c + 250, 860), (c - 250, 860)] + \
               [(2 * c - x, y) for x, y in reversed(sl)] + [(c - 250, 175), (c - 95, 120), (c, 150)]
        d.polygon(body, fill=255)
    return np.asarray(im) > 0


# ---------------- textures ----------------
def _fill_outside(rgb: np.ndarray, inside: np.ndarray) -> np.ndarray:
    """Colour outside the garment = nearest garment pixel (no background halo on the seams)."""
    from scipy import ndimage

    _, (iy, ix) = ndimage.distance_transform_edt(~inside, return_indices=True)
    return rgb[iy, ix]


def _crop(photo, mask: np.ndarray):
    m = clean_mask(mask)
    ys, xs = np.nonzero(m)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgb = np.asarray(photo.convert("RGB"))[y0:y1, x0:x1].astype(np.uint8)
    inside = m[y0:y1, x0:x1]
    return _fill_outside(rgb, inside), inside


def write(out, kind: str, ptype: str, photo=None, mask=None, back_photo=None, back_mask=None,
          colour: str | None = None, length: str | None = None, base_rgb=None) -> dict:
    """pattern.json + pattern_atlas.png (front panel texture | back panel texture, 1024 x 1024 each)."""
    import json
    from pathlib import Path

    from PIL import Image

    import garment_photo as gp

    out = Path(out)
    if mask is None:
        mask = default_mask(ptype, length)
    pat = build_pattern(mask, kind, ptype)
    mc = pat.pop("mask_clean")
    H, W = mc.shape
    S = 1024
    if photo is not None:
        x0, y0 = pat["offset_px"]
        photo = rotate_img(photo.convert("RGB"), pat.get("rotation_deg", 0.0))
        rgb = np.asarray(photo)[y0:y0 + H, x0:x0 + W].astype(np.uint8)
        front = gp.flatten(Image.fromarray(_fill_outside(rgb, mc)))
        base = np.asarray(base_rgb if base_rgb is not None else gp.main_colour(rgb[mc]), float)
        if back_photo is not None and back_mask is not None and back_mask.any():
            bm, bang, _ = prepare_mask(back_mask, kind, ptype)
            from PIL import Image as _I

            b_rgb, _ = _crop(rotate_img(back_photo.convert("RGB"), bang), bm)
            back = gp.flatten(Image.fromarray(b_rgb)).resize((W, H), Image.LANCZOS)
            back_mode = "photo"
        else:
            fa = np.asarray(front).astype(float)
            far = np.abs(fa - base).max(-1) > 40
            if far[mc].mean() > 0.45:  # all-over pattern (camo, floral, checks): it continues on the back
                back, back_mode = front, "all-over pattern"
            else:  # plain garment with a print on the front: plain back in the garment's colour
                from scipy import ndimage

                plain = fa.copy()
                plain[far] = base
                plain = np.stack([ndimage.median_filter(plain[..., k], size=5) for k in range(3)], -1)
                back, back_mode = Image.fromarray(plain.astype(np.uint8)), "main colour"
    else:
        hexc = (colour or "#808080").lstrip("#")
        rgbc = np.array([int(hexc[i:i + 2], 16) for i in (0, 2, 4)], float)
        noise = np.random.default_rng(0).normal(0, 3.0, (S, S, 1))  # a hint of fabric, not flat plastic
        flat = Image.fromarray(np.clip(rgbc + noise, 0, 255).astype(np.uint8))
        front = back = flat
        back_mode = "colour"
    atlas = Image.new("RGB", (2 * S, S))
    atlas.paste(front.resize((S, S), Image.LANCZOS), (0, 0))
    atlas.paste(back.resize((S, S), Image.LANCZOS), (S, 0))
    atlas.save(out / "pattern_atlas.png")
    pat.update({"atlas": "pattern_atlas.png", "back_texture": back_mode, "type": ptype})
    json.dump(pat, open(out / "pattern.json", "w"))
    return {"garment": pat["garment"], "vertices": len(pat["verts"]), "back_texture": back_mode}
