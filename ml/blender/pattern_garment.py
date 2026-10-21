"""Sew a garment from its 2D pattern around the avatar (Blender cloth), like CLO3D / Marvelous Designer.

pattern.json (from ml/scripts/m09/garment_pattern.py) = one panel outline (the garment laid flat), triangulated;
the front panel and the back panel share it. Each outline point is sewn (front to back) or an opening.

1. real size: panel width at the chest (tops) / hips (trousers) / waist (skirts) = half the garment's
   circumference from the size chart + fit ease (or from the body when no size is given)
2. the panels are placed on the avatar's frontal plane: shoulder line on the shoulders, waistband at the waist;
   sleeves and legs are turned to follow the avatar's arms and legs
3. each panel starts just outside the body (or the layers under it): the front one in front, the back one
   behind; below the bust / hips the fabric starts hanging straight down, as it will
4. Blender cloth: sewing springs close the seams, gravity and collisions drape it. Rest shape = the flat
   pattern (a shape key), so the garment keeps its real size whatever its starting shape
5. seams welded, surface smoothed; UVs = photo pixels (front photo on the front panel, back photo on the back)
"""

from __future__ import annotations

import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import garment_fit  # noqa: E402

SEWN, NECK, HEM, SLEEVE_END, WAIST, LEG_END, ARMHOLE = 0, 1, 2, 3, 4, 5, 6


def _smooth01(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _angle(v) -> float:
    return math.atan2(v[1], v[0])


def _wrap_pi(a: float) -> float:
    return (a + math.pi) % (2 * math.pi) - math.pi


def _rotate(p, c, a):
    x, y = p[0] - c[0], p[1] - c[1]
    ca, sa = math.cos(a), math.sin(a)
    return (c[0] + ca * x - sa * y, c[1] + sa * x + ca * y)


# ---------------- 1 + 2: size and placement on the frontal plane ----------------
def body_frame(body, meas: dict) -> dict:
    """Shoulder top height, hip / ankle joints (legs), body depth centre."""
    mw = body.matrix_world
    cx = meas["center_x"]
    pts = [mw @ v.co for v in body.data.vertices]
    sh = meas["shoulder_half"]
    tops = [p.z for p in pts if abs(abs(p.x - cx) - 0.6 * sh) < 0.02 and abs(p.y) < 0.12
            and meas["chest_z"] < p.z < meas["neck_z"] + 0.01]  # the shoulders, not the head
    shoulder_top = max(tops) if tops else meas["neck_z"] - 0.05
    legs = {}
    for side in ("l", "r"):
        hip = garment_fit._center(body, f"joint-{side}-upper-leg")
        ank = garment_fit._center(body, f"joint-{side}-foot") or garment_fit._center(body, f"joint-{side}-ankle")
        if hip and ank:
            legs[side] = (hip, ank)
    yc = sum(p.y for p in pts) / len(pts)
    return {"shoulder_top": shoulder_top, "legs": legs, "yc": yc, "floor_z": min(p.z for p in pts)}


def _length_target(pat: dict, tgt: dict, piece: dict) -> tuple[float, float] | None:
    """Plausible garment length range (m). Phone photos taken at an angle stretch the garment (perspective):
    the size chart's length is the reference, the photo may differ by +-15 %."""
    g = pat["garment"]
    if g == "top" and tgt.get("length_cm"):
        L = tgt["length_cm"] / 100
        return 0.85 * L, 1.15 * L
    if g == "pants":
        if (pat.get("type") or "").lower() == "shorts":
            return 0.38, 0.62
        if tgt.get("length_cm"):
            L = tgt["length_cm"] / 100 + 0.27  # inseam + rise = outseam
            return 0.88 * L, 1.1 * L
    if g == "skirt":
        L = {"mini": 0.42, "midi": 0.68, "long": 0.95}.get(piece.get("length") or "", None)
        if L:
            return 0.8 * L, 1.2 * L
    if g == "dress":
        return 0.8, 1.35
    return None


def place(pat: dict, piece: dict, meas: dict, frame: dict, sex: str):
    """Pattern pixels -> (X, Z) on the avatar's frontal plane (metres).
    Returns (base positions, per-triangle island (0 = body, 1 / 2 = sleeves), per-island transform, scale, info).
    Sleeves are separate islands (set-in sleeves, as real t-shirts are made): each is turned rigidly to follow its
    arm and sewn back to the armhole, so it never overlaps the body of the garment. Trouser legs bend in place."""
    info = pat["info"]
    g = pat["garment"]
    kind_chart = "bottom" if g in ("pants", "skirt") else "top"
    size, fit = piece.get("size"), piece.get("fit", "regular")
    if size:
        tgt = garment_fit.target_dims(sex, size, fit, kind_chart)
    else:  # template fit: the body + regular ease
        e = garment_fit.FIT.get(fit, garment_fit.FIT["regular"])[0]
        tgt = {"girth_cm": (meas["chest_cm"] if kind_chart == "top" else meas["hips_cm"]) + e,
               "waist_cm": meas["waist_cm"] + e * 0.3,
               "length_cm": None}
    if g == "skirt":
        s = (tgt.get("waist_cm", meas["waist_cm"] + 4) / 100 / 2) / max(1.0, info.get("waist_px", info["width_px"]))
    else:
        s = (tgt["girth_cm"] / 100 / 2) / max(1.0, info["width_px"])
    sv = s
    rng = _length_target(pat, tgt, piece)
    if g in ("pants", "skirt", "dress"):  # never below the floor (hem at least 1.5 cm above it)
        top_z = (meas["hips_z"] + 0.75 * (meas["waist_z"] - meas["hips_z"])) if g != "dress" else             frame["shoulder_top"] + 0.012
        floor_max = top_z - frame.get("floor_z", 0.0) - 0.015
        rng = (min(rng[0], floor_max * 0.95), min(rng[1], floor_max)) if rng else (0.3, floor_max)
    photo_len = (info["y1"] - info["anchor_y"]) * s
    if rng and photo_len > 0:
        sv = s * min(max(photo_len, rng[0]), rng[1]) / photo_len
    cx_body = meas["center_x"]
    if g in ("pants", "skirt"):
        z0 = meas["hips_z"] + 0.75 * (meas["waist_z"] - meas["hips_z"])  # where trousers sit
    else:
        z0 = frame["shoulder_top"] + 0.012
    ay, pcx = info["anchor_y"], info["cx"]
    V = pat["verts"]
    base = [(cx_body + (x - pcx) * s, z0 - (y - ay) * sv) for x, y in V]
    tris = pat["tris"]
    tri_island = [0] * len(tris)
    tf = {0: None}
    rotated = 0
    if g in ("top", "dress") and info.get("sleeves"):
        bx = {"L": info["cx"] - info["bw"] / 2, "R": info["cx"] + info["bw"] / 2}
        H = info["y1"] - info["y0"]
        for k, t in enumerate(tris):
            cxp = sum(V[q][0] for q in t) / 3
            cyp = sum(V[q][1] for q in t) / 3
            for side, isl in (("L", 1), ("R", 2)):
                if side not in info["sleeves"]:
                    continue
                beyond = cxp < bx["L"] if side == "L" else cxp > bx["R"]
                if beyond and cyp < info["armpit"][side] + 0.02 * H:
                    tri_island[k] = isl
        for side, isl in (("L", 1), ("R", 2)):
            sl = info["sleeves"].get(side)
            arm = None
            for a, b in meas.get("arms", {}).values():
                if (a.x - cx_body < 0) == (side == "L"):
                    arm = (a, b)
            if not sl or not arm:
                continue
            a, b = arm
            # pivot: top of the armhole (where the shoulder seam meets the sleeve)
            px_side = bx[side]
            top_y = min((V[q][1] for q in pat["boundary"] if abs(V[q][0] - px_side) < 0.03 * info["bw"]),
                        default=info["anchor_y"])
            S = (cx_body + (px_side - pcx) * s, z0 - (top_y - ay) * sv)
            R = (cx_body + (sl["root"][0] - pcx) * s, z0 - (sl["root"][1] - ay) * sv)
            dS = (sl["dir"][0] * s, -sl["dir"][1] * sv)
            n = math.hypot(*dS)
            dS = (dS[0] / n, dS[1] / n)
            dA = (b.x - a.x, b.z - a.z)
            n = math.hypot(*dA)
            dA = (dA[0] / n, dA[1] / n)
            rot = _wrap_pi(_angle(dA) - _angle(dS))
            R2 = _rotate(R, S, rot)
            ar = (a.x - R2[0], a.z - R2[1])
            along = ar[0] * dA[0] + ar[1] * dA[1]
            off = (ar[0] - along * dA[0], ar[1] - along * dA[1])
            # keep the sleeve's top at least where it was (no sleeve sunk into the shoulder)
            tf[isl] = (S, rot, off)
            rotated += 1
    elif g == "pants":
        for side, lg in info.get("legs", {}).items():
            leg = None
            for a, b in frame["legs"].values():
                if (a.x - cx_body < 0) == (side == "L"):
                    leg = (a, b)
            if not leg:
                continue
            a, b = leg
            R = (cx_body + (lg["root"][0] - pcx) * s, z0 - (lg["root"][1] - ay) * sv)
            dS = (lg["dir"][0] * s, -lg["dir"][1] * sv)
            n = math.hypot(*dS)
            dS = (dS[0] / n, dS[1] / n)
            dA = (b.x - a.x, b.z - a.z)
            n = math.hypot(*dA)
            dA = (dA[0] / n, dA[1] / n)
            rot = _wrap_pi(_angle(dA) - _angle(dS))
            ar = (a.x - R[0], a.z - R[1])
            along = ar[0] * dA[0] + ar[1] * dA[1]
            off = (ar[0] - along * dA[0], ar[1] - along * dA[1])
            for k, p in enumerate(base):
                t = (p[0] - R[0]) * dS[0] + (p[1] - R[1]) * dS[1]
                if t <= 0 or (p[0] - cx_body) * (R[0] - cx_body) < 0:
                    continue
                w = _smooth01(t / 0.12)
                q = _rotate(p, R, rot * w)
                base[k] = (q[0] + off[0] * w, q[1] + off[1] * w)
                rotated += 1
    return base, tri_island, tf, s, {"scale_m_per_px": round(s, 5), "scale_v": round(sv, 5), "z0": round(z0, 3),
                                    "rotated": rotated, "girth_cm": tgt.get("girth_cm"),
                                    "length_m": round((info["y1"] - info["anchor_y"]) * sv, 3)}


def apply_tf(p, t):
    if t is None:
        return p
    S, rot, off = t
    q = _rotate(p, S, rot)
    return (q[0] + off[0], q[1] + off[1])


def _girth_at(body, z: float) -> float:
    """Circumference of the convex hull of the body's horizontal slice at height z."""
    mw = body.matrix_world
    pts = sorted({(round(p.x, 4), round(p.y, 4)) for p in (mw @ v.co for v in body.data.vertices) if abs(p.z - z) < 0.012})
    if len(pts) < 8:
        return 0.8

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    return sum(math.dist(hull[i], hull[(i + 1) % len(hull)]) for i in range(len(hull)))


# ---------------- 3: starting shape just outside the body / inner layers ----------------
def _bvh(objs: list):
    dg = bpy.context.evaluated_depsgraph_get()
    return [(o, BVHTree.FromObject(o, dg)) for o in objs]


def _ray(trees, origin: Vector, direction: Vector):
    best = None
    for o, t in trees:
        inv = o.matrix_world.inverted()
        lo = inv @ origin
        ld = (inv.to_3x3() @ direction).normalized()
        hit = t.ray_cast(lo, ld, 10.0)
        if hit[0] is not None:
            w = o.matrix_world @ hit[0]
            d = (w - origin).length
            if best is None or d < best[1]:
                best = (w, d)
    return best[0] if best else None


def start_shape(P: list, pat: dict, obstacles_torso: list, obstacles_all: list, frame: dict, offset: float):
    """Starting y of each panel (the CLO3D / Marvelous "arrangement", as in Blender sewing tutorials): two FLAT
    panels, the front one in front of everything it covers (body, arms, layers under it), the back one behind.
    Flat, so the cloth's rest lengths (taken from the starting shape) are the real pattern; sewing springs then
    pull the seams together around the body, gravity drapes it. Nothing is crossed at the start."""
    s_all = _bvh(obstacles_all)
    yc = frame["yc"]
    hits_f, hits_b = [], []
    for X, Z in P:
        hf = _ray(s_all, Vector((X, yc - 3.0, Z)), Vector((0, 1, 0)))
        hb = _ray(s_all, Vector((X, yc + 3.0, Z)), Vector((0, -1, 0)))
        if hf:
            hits_f.append(hf.y)
        if hb:
            hits_b.append(hb.y)
    yF = min(hits_f, default=yc - 0.15) - offset
    yB = max(hits_b, default=yc + 0.15) + offset
    return [yF] * len(P), [yB] * len(P)


# ---------------- 4: mesh + cloth ----------------
def layout(pat: dict, base: list, tri_island: list, tf: dict):
    """Per panel vertex list with sleeve islands split off: [(orig index, island, (X, Z))], triangles remapped,
    and the sewing pairs (index pairs within ONE panel: armhole seams) + boundary copies for front-back seams."""
    keys, index = [], {}
    tris = []
    for t, isl in zip(pat["tris"], tri_island):
        tri = []
        for q in t:
            k = (q, isl)
            if k not in index:
                index[k] = len(keys)
                keys.append(k)
            tri.append(index[k])
        tris.append(tri)
    pos = [apply_tf(base[q], tf.get(isl)) for q, isl in keys]
    armhole = []  # same pattern point, body copy <-> sleeve copy
    for (q, isl), k in index.items():
        if isl != 0 and (q, 0) in index:
            armhole.append((index[(q, 0)], k))
    return keys, pos, tris, armhole


def make_mesh(name: str, pat: dict, keys: list, pos: list, tris: list, armhole: list, front_y: list,
              back_y: list):
    m = len(keys)
    verts = [(X, front_y[i], Z) for i, (X, Z) in enumerate(pos)] + [(X, back_y[i], Z) for i, (X, Z) in enumerate(pos)]
    faces = [tuple(t[::-1]) for t in tris] + [tuple(k + m for k in t) for t in tris]  # front faces -Y, back +Y
    sewn = {q for q in pat["boundary"] if pat["open"][q] == SEWN}
    sew = [(k, k + m) for k, (q, _isl) in enumerate(keys) if q in sewn]  # front <-> back
    sew += [(a, b) for a, b in armhole] + [(a + m, b + m) for a, b in armhole]  # sleeve <-> armhole
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, sew, faces)
    me.update()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    # UVs = photo pixels: front panel on the left half of the atlas, back panel on the right half
    W, H = pat["size_px"]
    uv = me.uv_layers.new(name="photo")
    nt = len(tris)
    for poly in me.polygons:
        back = poly.index >= nt
        for li in poly.loop_indices:
            q = keys[me.loops[li].vertex_index % m][0]
            x, y = pat["verts"][q]
            uv.data[li].uv = ((0.5 if back else 0.0) + 0.5 * min(1.0, max(0.0, x / W)), 1.0 - min(1.0, max(0.0, y / H)))
    return obj


def add_rest_shape(obj, P: list) -> None:
    """Rest shape = the flat pattern (both panels on the same flat outline). Added last: once a mesh has shape
    keys, moving its vertices directly no longer changes its shape."""
    n = len(P)
    obj.shape_key_add(name="Basis", from_mix=False)
    flat = obj.shape_key_add(name="flat", from_mix=False)
    for i, (X, Z) in enumerate(P):
        flat.data[i].co = (X, 0.0, Z)
        flat.data[i + n].co = (X, 0.0, Z)


def material(obj, atlas: str) -> None:
    img = bpy.data.images.load(atlas, check_existing=True)
    img.reload()
    mat = bpy.data.materials.new(f"fabric_{obj.name}")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.85
    for name, val in (("Sheen Weight", 0.35), ("Sheen Roughness", 0.6)):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = val
    uvn = nt.nodes.new("ShaderNodeUVMap")
    uvn.uv_map = "photo"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "EXTEND"
    nt.links.new(uvn.outputs["UV"], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def simulate(obj, pat: dict, obstacles: list, gsm: float, frames: int = 50, sewing_phase: bool = True) -> dict:
    import cloth_sim

    for o in obstacles:
        cloth_sim.add_collider(o, 0.003)
    f = garment_fit.fabric(gsm)
    n = len(obj.data.vertices) // 2
    g = pat["garment"]
    cloth = obj.modifiers.new("cloth", "CLOTH")
    st = cloth.settings
    st.quality = 10
    st.mass = f["mass"]
    st.air_damping = 1.0
    st.tension_stiffness = st.shear_stiffness = f["tension"]
    # real fabric resists in-plane compression and buckles out of plane (folds); a low compression stiffness
    # let it crumple in its own plane into stacks of mesh-aligned pleats (tested)
    st.compression_stiffness = f["tension"]
    st.bending_stiffness = f["bending"]
    st.tension_damping = st.compression_damping = st.shear_damping = 5.0
    st.use_sewing_springs = True
    st.sewing_force_max = 15.0  # gentle: an unlimited sewing pull crumples the panels (tested)
    if g in ("pants", "skirt"):  # elastic waistband: it grips the waist / hips and holds the garment up
        band = obj.vertex_groups.new(name="waistband")
        zs = [obj.data.vertices[i].co.z for i in range(n)]
        top = max(zs)
        for i, z in enumerate(zs):
            if z > top - 0.035:
                band.add([i, i + n], 1.0, "REPLACE")
        # shrink just enough for the band to grip the body where it sits (elastic / belt)
        info = pat["info"]
        waist_px = info.get("waist_px", info["width_px"])
        garment_waist = 2 * waist_px * pat["_scale"]
        body_waist = pat["_body_waist"]
        st.shrink_min = 0.0
        st.shrink_max = min(0.45, max(0.04, 1.0 - 1.02 * body_waist / max(1e-3, garment_waist)))
        st.vertex_group_shrink = band.name
    cs = cloth.collision_settings
    cs.collision_quality = 5
    cs.distance_min = 0.004
    cs.use_self_collision = False
    cloth.point_cache.frame_start, cloth.point_cache.frame_end = 1, frames
    # sewing first (no gravity: the panels would fall before the seams close), then gravity drapes the garment
    ew = st.effector_weights
    if sewing_phase:
        sew_frames = max(8, frames // 3)
        ew.gravity = 0.0
        ew.keyframe_insert("gravity", frame=1)
        ew.gravity = 0.0
        ew.keyframe_insert("gravity", frame=sew_frames)
        ew.gravity = 1.0
        ew.keyframe_insert("gravity", frame=sew_frames + 6)
    else:  # settling an already sewn garment
        ew.gravity = 1.0
    sc = bpy.context.scene
    for fr in range(1, frames + 1):
        sc.frame_set(fr)
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    new = bpy.data.meshes.new_from_object(ev)
    old = obj.data
    obj.modifiers.clear()
    obj.data = new
    bpy.data.meshes.remove(old)
    sc.frame_set(1)
    for o in obstacles:
        cloth_sim.remove_collider(o)
    return {"frames": frames}


# ---------------- 5: finishing ----------------
def finish(obj, pat: dict) -> dict:
    """Weld every pair of vertices joined by a sewing edge (front-back seams and armholes), remove the sewing
    edges, smooth shading + one level of subdivision."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    loose = [e for e in bm.edges if not e.link_faces]
    parent = {}

    def find(v):
        while parent.get(v, v) is not v:
            v = parent[v]
        return v

    for e in loose:
        a, b = find(e.verts[0]), find(e.verts[1])
        if a is not b:
            parent[b] = a
    groups = {}
    for v in list(parent):
        groups.setdefault(find(v), []).append(v)
    targets = {}
    for root, members in groups.items():
        allv = [root] + [v for v in members if v is not root]
        c = sum((v.co for v in allv), allv[0].co * 0) / len(allv)
        root.co = c
        for v in allv[1:]:
            targets[v] = root
    bmesh.ops.delete(bm, geom=loose, context="EDGES")
    bmesh.ops.weld_verts(bm, targetmap=targets)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    for p in obj.data.polygons:
        p.use_smooth = True
    sub = obj.modifiers.new("smooth_surface", "SUBSURF")
    sub.levels = sub.render_levels = 1
    sub.uv_smooth = "PRESERVE_BOUNDARIES"
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=sub.name)
    return {"welded": len(targets), "vertices": len(obj.data.vertices)}


def limb_trimmed(collider, meas: dict, from_t: float, name: str = "collider_trim"):
    """Copy of the body collider without the forearms + hands (from `from_t` of the shoulder -> hand line: 0.45 =
    from just above the elbow, 0.85 = the hands only). In the A-pose the hands hang next to the hips: the side
    seams of a wide top would close around them while sewing. The arm part is found by growing over the mesh
    from the hand, staying close to the arm's axis: it never reaches the hips or the waist (cutting by distance
    alone made holes in the body's sides, and the garment slipped through them)."""
    tr = collider.copy()
    tr.data = collider.data.copy()
    tr.name = name
    bpy.context.collection.objects.link(tr)
    for m in list(tr.modifiers):
        tr.modifiers.remove(m)
    bm = bmesh.new()
    bm.from_mesh(tr.data)
    bm.verts.ensure_lookup_table()
    mw = tr.matrix_world
    pos = [mw @ v.co for v in bm.verts]
    drop = set()
    for a, b in meas.get("arms", {}).values():
        ab = b - a
        start = a + ab * from_t
        end = b + ab.normalized() * 0.16  # fingers
        seg = end - start

        def dist(p, start=start, seg=seg):
            t = max(0.0, min(1.0, (p - start).dot(seg) / seg.length_squared))
            return (p - (start + seg * t)).length, (p - start).dot(seg) / seg.length_squared

        seed = min(range(len(pos)), key=lambda k: (pos[k] - b).length)
        todo, seen = [seed], {seed}
        while todo:
            k = todo.pop()
            d, t = dist(pos[k])
            if d > 0.075 or t < 0.0:
                continue
            drop.add(k)
            for e in bm.verts[k].link_edges:
                o = e.other_vert(bm.verts[k]).index
                if o not in seen:
                    seen.add(o)
                    todo.append(o)
    bmesh.ops.delete(bm, geom=[bm.verts[k] for k in drop], context="VERTS")
    bm.to_mesh(tr.data)
    bm.free()
    tr.hide_render = True
    return tr


def build(pattern_path: str, piece: dict, meas: dict, body, collider, trunk, inner: list, sex: str, name: str,
          frames: int = 60) -> tuple:
    pat = json.load(open(pattern_path))
    frame = body_frame(body, meas)
    base, tri_island, tf, s, info = place(pat, piece, meas, frame, sex)
    pat["_scale"] = s
    pat["_body_waist"] = _girth_at(collider, info["z0"] - 0.02)
    keys, pos, tris, armhole = layout(pat, base, tri_island, tf)
    info["sleeve_islands"] = sum(1 for k in tf if k)
    offset = 0.012 + (0.006 if inner else 0.0)
    fy, by = start_shape(pos, pat, [trunk] + inner, [collider] + inner, frame, offset + 0.03)
    obj = make_mesh(name, pat, keys, pos, tris, armhole, fy, by)
    import cloth_sim

    info["lifted_start"] = cloth_sim.push_outside(obj, [collider] + inner, gap=0.006)
    material(obj, os.path.join(os.path.dirname(pattern_path), pat.get("atlas", "pattern_atlas.png")))
    gsm = piece.get("gsm") or {"pants": 300, "skirt": 180, "dress": 160}.get(pat["garment"], 170)
    sim_body = collider
    if pat["garment"] in ("top", "dress"):
        sl = pat["info"].get("sleeves", {})
        long_sleeves = any(v.get("length", 0) * s > 0.33 for v in sl.values())
        sim_body = limb_trimmed(collider, meas, 0.85 if long_sleeves else 0.45)
    if frames > 0:
        # sewn and draped on the BODY alone (CLO / Marvelous: one layer at a time); sewing around another garment
        # makes the hem catch on its waistband edge (tested)
        info["sim"] = simulate(obj, pat, [sim_body], gsm, frames)
    if inner:
        # then over the layers under it: lifted just outside them, and a short settle with them as obstacles
        info["lifted_over_inner"] = cloth_sim.push_outside(obj, inner, gap=0.008)
        if frames > 0:
            info["settle_over_inner"] = simulate(obj, pat, [sim_body] + inner, gsm, 20, sewing_phase=False)
    if sim_body is not collider:
        bpy.data.objects.remove(sim_body, do_unlink=True)
        info["final_push"] = cloth_sim.push_outside(obj, [collider], gap=0.004)
    if inner:
        info["final_push_inner"] = cloth_sim.push_outside(obj, inner, gap=0.005)
    else:  # debugging: the starting shape only
        pass
    info.update(finish(obj, pat))
    return obj, info
