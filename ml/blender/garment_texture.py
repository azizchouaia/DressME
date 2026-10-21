"""Put the garment photo (atlas from ml/scripts/m09/garment_photo.py) on the 3D template. Runs in Blender.

Front-facing faces get the front photo, back-facing faces the back photo (or the main colour). Each sleeve
is projected along its arm (shoulder -> sleeve end, top -> bottom of the arm) onto its own photo crop, and
each trouser leg along the leg onto its straightened photo strip. Projection = straight front view of the
body of the garment, done on the final (resized, draped) shape: no distortion, and a print still grows with
an XXXL garment. The template's own texture is kept as fabric relief.
"""

from __future__ import annotations

import json
import math
import os

import bpy
from mathutils import Vector

V0 = 1 / 3  # atlas v2 (2048 x 1536): bodies in v [1/3, 1], the 4 sleeve squares in v [0, 1/3]
SLEEVE_BOX = {("front", "L"): 0, ("front", "R"): 1, ("back", "L"): 2, ("back", "R"): 3}


def apply(garment, meas: dict, info_path: str, kind: str = "top") -> dict:
    info = json.load(open(info_path))
    if info.get("layout") == "legs":
        return _apply_legs(garment, meas, info, info_path)
    mw = garment.matrix_world
    pts = [mw @ v.co for v in garment.data.vertices]
    cx = meas["center_x"]
    zs = [p.z for p in pts]
    z_bot, z_top = min(zs), max(zs)
    tops = kind in ("top", "outerwear", "dress")
    if tops:
        hem = [abs(p.x - cx) for p in pts if p.z < z_bot + 0.15 * (z_top - z_bot)]
        half = max(hem) if hem else meas["shoulder_half"]
        z_top = max(p.z for p in pts if abs(p.x - cx) < half * 0.5)  # collar height at the centre
    else:
        half = max(abs(p.x - cx) for p in pts)

    # sleeves: which vertices, and their position along / across their arm
    arms = meas.get("arms", {})
    sleeve = {}  # vertex index -> (side "L"/"R", along, across)
    if tops and arms and kind != "dress":
        segs = {("L" if (a.x - cx) < 0 else "R"): (a, b) for a, b in arms.values()}
        for i, p in enumerate(pts):
            side = "L" if p.x < cx else "R"
            if abs(p.x - cx) <= half * 1.03 or side not in segs:
                continue
            a, b = segs[side]
            ab = b - a
            t = (p - a).dot(ab) / ab.length_squared
            axis = a + ab * max(0.0, min(1.0, t))
            d = ab.normalized()
            up = Vector((-d.z, 0.0, d.x)) if d.x * (1 if side == "R" else -1) >= 0 else Vector((d.z, 0.0, -d.x))
            if up.z < 0:
                up = -up
            sleeve[i] = (side, t, (p - axis).dot(up))
        rng = {}
        for side in ("L", "R"):
            vals = [v for v in sleeve.values() if v[0] == side]
            if vals:
                rng[side] = (min(v[1] for v in vals), max(v[1] for v in vals), max(abs(v[2]) for v in vals) or 1e-3)

    uv = garment.data.uv_layers.get("photo") or garment.data.uv_layers.new(name="photo")
    rot = mw.to_3x3()
    n_sleeve = 0
    for poly in garment.data.polygons:
        face = "back" if (rot @ poly.normal).y > 0 else "front"  # the front of an MPFB body faces -Y
        for li in poly.loop_indices:
            vi = garment.data.loops[li].vertex_index
            p = pts[vi]
            if vi in sleeve:
                side, t, off = sleeve[vi]
                t0, t1, r = rng[side]
                along = (t - t0) / (t1 - t0) if t1 > t0 else 0.0  # 0 at the shoulder seam, 1 at the sleeve end
                u_img = 1 - along if side == "L" else along  # in the photo the shoulder is on the body side
                v_img = 0.5 + 0.5 * max(-1.0, min(1.0, off / r))  # top of the arm = top of the sleeve photo
                k = SLEEVE_BOX[(face, side)]
                uv.data[li].uv = (0.25 * k + 0.25 * min(1.0, max(0.0, u_img)), V0 * v_img)
                n_sleeve += 1
                continue
            u = min(1.0, max(0.0, (p.x - (cx - half)) / (2 * half)))
            v = min(1.0, max(0.0, (p.z - z_bot) / (z_top - z_bot)))
            uv.data[li].uv = ((0.5 if face == "back" else 0.0) + 0.5 * u, V0 + (1 - V0) * v)
    atlas = info["atlas"]
    if not os.path.isabs(atlas) or not os.path.exists(atlas):  # the atlas always sits next to info.json
        atlas = os.path.join(os.path.dirname(os.path.abspath(info_path)), "atlas.png")
    _material(garment, atlas)
    return {"main_color": info["main_color"], "has_back_photo": info["has_back_photo"], "sleeve_loops": n_sleeve,
            "sleeve_photos": info.get("sleeve_photos")}


def _atlas_path(info: dict, info_path: str) -> str:
    atlas = info["atlas"]
    if not os.path.isabs(atlas) or not os.path.exists(atlas):  # the atlas always sits next to info.json
        atlas = os.path.join(os.path.dirname(os.path.abspath(info_path)), "atlas.png")
    return atlas


LEG_V = 0.75  # atlas "legs": upper parts in v [0.75, 1], the four leg strips in v [0, 0.75] (hip at the top)


def _apply_legs(garment, meas: dict, info: dict, info_path: str) -> dict:
    """Trousers / shorts: above the crotch = front view of the upper part; below = each leg on its own strip,
    along = crotch -> hem of that leg, across = image-left -> image-right edge of the leg at that height (the
    photo strips are straightened the same way). Decided per face, so no face spans two parts of the atlas."""
    mw = garment.matrix_world
    pts = [mw @ v.co for v in garment.data.vertices]
    cx = meas["center_x"]
    z_top = max(p.z for p in pts)
    centre = [p.z for p in pts if abs(p.x - cx) < 0.012]
    crotch_z = min(centre) if centre else meas["hips_z"] - 0.1
    # each leg in its own frame: along its axis (PCA of the leg, pointing down) and across it (in the front
    # plane); legs stand apart in the A-pose, so their rings are tilted and slicing by height would cut them
    import numpy as np

    frame = {}
    for sd in ("L", "R"):
        leg = np.array([(p.x, p.y, p.z) for p in pts if p.z < crotch_z and (p.x < cx) == (sd == "L")])
        if len(leg) < 8:
            continue
        mu = leg.mean(0)
        _, vecs = np.linalg.eigh(np.cov((leg - mu).T))
        d = vecs[:, -1]
        if d[2] > 0:
            d = -d
        a = np.array([-d[2], 0.0, d[0]])
        a /= np.linalg.norm(a) or 1
        if a[0] < 0:
            a = -a
        s_ = (leg - mu) @ d
        c_ = (leg - mu) @ a
        bins = ((s_ - s_.min()) / 0.01).astype(int)
        ks = sorted(set(bins.tolist()))
        lo = np.array([c_[bins == k].min() for k in ks])
        hi = np.array([c_[bins == k].max() for k in ks])
        allk = np.arange(0, ks[-1] + 1)
        lo_i, hi_i = np.interp(allk, ks, lo), np.interp(allk, ks, hi)
        # the template's rings are not exactly perpendicular to the leg axis: a 1 cm slice holds only part of a
        # ring, so the width is the envelope over +-3 cm
        w = 3
        lo_e = np.array([lo_i[max(0, k - w):k + w + 1].min() for k in range(len(allk))])
        hi_e = np.array([hi_i[max(0, k - w):k + w + 1].max() for k in range(len(allk))])
        b = np.cross(d, a)  # the third axis, made to point to the front of the body (-Y)
        if b[1] > 0:
            b = -b
        frame[sd] = {"mu": mu, "d": d, "a": a, "b": b, "s0": float(s_.min()), "s1": float(s_.max()), "lo": lo_e,
                     "hi": hi_e}

    up = [abs(p.x - cx) for p in pts if p.z >= crotch_z]
    half_up = max(up) if up else meas["shoulder_half"]
    uv = garment.data.uv_layers.get("photo") or garment.data.uv_layers.new(name="photo")
    rot = mw.to_3x3()
    n_leg = 0
    for poly in garment.data.polygons:
        face = "back" if (rot @ poly.normal).y > 0 else "front"
        c = mw @ poly.center
        in_leg = c.z < crotch_z
        side = "L" if c.x < cx else "R"
        for li in poly.loop_indices:
            p = pts[garment.data.loops[li].vertex_index]
            if in_leg and side in frame:
                f = frame[side]
                q = np.array((p.x, p.y, p.z)) - f["mu"]
                sv = float(q @ f["d"])
                along = min(1.0, max(0.0, (sv - f["s0"]) / max(1e-3, f["s1"] - f["s0"])))
                # a flat-lay photo is the fabric unrolled: map by the angle around the leg, front photo on the
                # front half, back photo on the back half, the two meeting on the side seams (no stretched edge)
                cq = np.array((c.x, c.y, c.z)) - f["mu"]
                k_ = min(len(f["lo"]) - 1, max(0, int((sv - f["s0"]) / 0.01)))
                mid = (f["lo"][k_] + f["hi"][k_]) / 2
                x_ = float(q @ f["a"]) - mid
                y_ = float(q @ f["b"])
                face = "front" if float(cq @ f["b"]) > 0 else "back"
                if face == "front":
                    phi = math.atan2(max(y_, 0.0), x_)  # 0 (image right) .. pi (image left)
                    u_img = 1.0 - phi / math.pi
                else:
                    phi = math.atan2(min(y_, 0.0), x_)  # 0 .. -pi
                    u_img = 1.0 + phi / math.pi
                u_img = 0.04 + 0.92 * min(1.0, max(0.0, u_img))  # the photo's outline stays out
                k = SLEEVE_BOX[(face, side)]
                uv.data[li].uv = (0.25 * k + 0.25 * u_img, LEG_V * (1.0 - along))
                n_leg += 1
            else:
                u = min(1.0, max(0.0, (p.x - (cx - half_up)) / (2 * half_up)))
                v = min(1.0, max(0.0, (p.z - crotch_z) / max(1e-3, z_top - crotch_z)))
                uv.data[li].uv = ((0.5 if face == "back" else 0.0) + 0.5 * u, LEG_V + (1 - LEG_V) * v)
    _material(garment, _atlas_path(info, info_path))
    return {"main_color": info["main_color"], "has_back_photo": info["has_back_photo"], "leg_loops": n_leg,
            "crotch_z": round(crotch_z, 3)}


def _material(garment, atlas: str) -> None:
    img = bpy.data.images.load(atlas, check_existing=True)
    img.reload()  # the same path may hold a newer atlas (piece re-processed) than the one cached in this session
    old = garment.material_slots[0].material if garment.material_slots else None
    mat = bpy.data.materials.new(f"photo_{garment.name}")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.8
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "photo"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "EXTEND"
    nt.links.new(uvn.outputs["UV"], tex.inputs["Vector"])
    out = tex.outputs["Color"]
    # fabric relief: brightness of the template's own texture (its own UVs), 0.85..1.05
    old_tex = None
    if old and old.use_nodes:
        old_tex = next((n for n in old.node_tree.nodes if n.type == "TEX_IMAGE" and n.image), None)
    if old_tex is not None:
        rel = nt.nodes.new("ShaderNodeTexImage")
        rel.image = old_tex.image
        ruv = nt.nodes.new("ShaderNodeUVMap")
        ruv.uv_map = garment.data.uv_layers[0].name
        nt.links.new(ruv.outputs["UV"], rel.inputs["Vector"])
        bw = nt.nodes.new("ShaderNodeRGBToBW")
        rng = nt.nodes.new("ShaderNodeMapRange")
        rng.inputs["To Min"].default_value, rng.inputs["To Max"].default_value = 0.85, 1.05
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type, mix.blend_type = "RGBA", "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        nt.links.new(rel.outputs["Color"], bw.inputs[0])
        nt.links.new(bw.outputs[0], rng.inputs["Value"])
        nt.links.new(out, mix.inputs[6])
        nt.links.new(rng.outputs["Result"], mix.inputs[7])
        out = mix.outputs[2]
    nt.links.new(out, bsdf.inputs["Base Color"])
    garment.data.materials.clear()
    garment.data.materials.append(mat)
