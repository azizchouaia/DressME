"""Size, fit and fabric for 3D garments: a size XXXL t-shirt on a small body must hang like a dress.

Runs inside Blender. Steps for one garment already fitted on the body by MPFB (body-hugging template):
  1. measure the body (chest / waist / hips: tape-measure = convex hull of the body slice) and the garment;
  2. target garment dimensions = size chart (XS..XXXL, men / women) + fit ease (slim / regular / oversize);
  3. scale the garment around its anchor (shoulders for tops, waist for bottoms): wider and longer or narrower;
  4. push any part that ends up inside the body back outside;
  5. short cloth simulation with body collision so the garment falls onto the body; the grammage (g/m2)
     sets the fabric's mass and stiffness (a 140 g/m2 tee is fluid, a 400 g/m2 hoodie is stiff).
"""

from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Vector

# Body measurements (cm) each letter size is made for. Typical EU / international charts.
SIZES = ("XXS", "XS", "S", "M", "L", "XL", "XXL", "XXXL", "4XL")
CHART = {
    "female": {"chest": (78, 82, 86, 92, 98, 104, 112, 120, 128), "waist": (60, 64, 68, 74, 80, 86, 94, 102, 110),
               "hips": (86, 90, 94, 100, 106, 112, 120, 128, 136),
               "top_length": (58, 60, 62, 64, 66, 68, 70, 72, 74),  # t-shirt, from the neck point
               "inseam": (76, 77, 78, 79, 80, 81, 82, 83, 84)},
    "male": {"chest": (82, 86, 92, 100, 108, 116, 124, 132, 140), "waist": (68, 72, 78, 86, 94, 102, 110, 118, 126),
             "hips": (86, 90, 96, 102, 108, 114, 120, 126, 132),
             "top_length": (64, 66, 69, 72, 75, 78, 80, 82, 84),
             "inseam": (78, 79, 80, 81, 82, 83, 84, 85, 86)},
}
# Extra room the garment has over the body (cm of circumference), and extra length (cm).
FIT = {"slim": (4, -2), "regular": (10, 0), "relaxed": (16, 3), "oversize": (26, 7)}
TOPS = {"top", "outerwear", "dress"}
BOTTOMS = {"bottom"}


# ---------------- measuring ----------------
def _center(obj, group: str) -> Vector | None:
    vg = obj.vertex_groups.get(group)
    if vg is None:
        return None
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices if any(g.group == vg.index for g in v.groups)]
    return sum(pts, Vector()) / len(pts) if pts else None


def _evaluated_points(obj) -> list[Vector]:
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    pts = [obj.matrix_world @ v.co for v in me.vertices]
    ev.to_mesh_clear()
    return pts


def _hull_perimeter(points: list[tuple[float, float]]) -> float:
    pts = sorted(set(points))
    if len(pts) < 3:
        return 0.0

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


def girth(obj, z: float, half_width: float, band: float = 0.012) -> float:
    """Tape-measure circumference (m) of the object around height z, keeping |x| < half_width (no arms)."""
    pts = [(p.x, p.y) for p in _evaluated_points(obj) if abs(p.z - z) < band and abs(p.x) < half_width]
    return _hull_perimeter(pts)


def max_girth(obj, z_lo: float, z_hi: float, half_width: float, step: float = 0.01) -> float:
    """Largest tape-measure circumference between two heights (hips are not at one exact height)."""
    pts = _evaluated_points(obj)
    best, z = 0.0, z_lo
    while z <= z_hi:
        ring = [(p.x, p.y) for p in pts if abs(p.z - z) < 0.008 and abs(p.x) < half_width]
        best = max(best, _hull_perimeter(ring))
        z += step
    return best


def body_landmarks(body) -> dict:
    j = {k: _center(body, f"joint-{k}") for k in ("neck", "l-shoulder", "r-shoulder", "spine-2", "pelvis",
                                                     "l-upper-leg", "r-upper-leg", "l-knee", "l-ankle", "ground")}
    nip = _center(body, "nippleTip")
    shoulder_half = abs(j["l-shoulder"].x - j["r-shoulder"].x) / 2
    chest_z = nip.z if nip else j["neck"].z - 0.6 * (j["neck"].z - j["spine-2"].z)
    hips_z = (j["l-upper-leg"].z + j["pelvis"].z) / 2
    arms = {}
    for side in ("l", "r"):
        sh, wr = _center(body, f"joint-{side}-shoulder"), _center(body, f"joint-{side}-hand")
        if sh and wr:
            arms[side] = (sh, wr)
    return {"arms": arms, "neck_z": j["neck"].z, "chest_z": chest_z, "waist_z": j["spine-2"].z, "hips_z": hips_z,
            "ankle_z": j["l-ankle"].z, "knee_z": j["l-knee"].z, "shoulder_half": shoulder_half, "center_x": (j["l-shoulder"].x + j["r-shoulder"].x) / 2}


def measure_body(body) -> dict:
    lm = body_landmarks(body)
    w = lm["shoulder_half"] * 0.95  # arms hang outside this in the A-pose
    return {"chest_cm": round(girth(body, lm["chest_z"], w) * 100, 1),
            "waist_cm": round(girth(body, lm["waist_z"], w) * 100, 1),
            "hips_cm": round(max_girth(body, lm["hips_z"] - 0.06, lm["waist_z"] - 0.03, w * 1.25) * 100, 1), **lm}


# ---------------- multi-part assets ----------------
def extract_part(obj, rule: str, meas: dict) -> int:
    """Keep one piece of a multi-part MakeHuman outfit. "largest": biggest connected piece (the jacket of a
    suit, without trousers, tie, shirt front, buttons). "above_belt": what is above the belt (the shirt of a
    shirt + jeans outfit)."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.verts.ensure_lookup_table()
    if rule == "largest":
        seen, comps = set(), []
        for v in bm.verts:
            if v.index in seen:
                continue
            stack, comp = [v], []
            seen.add(v.index)
            while stack:
                x = stack.pop()
                comp.append(x)
                for e in x.link_edges:
                    y = e.other_vert(x)
                    if y.index not in seen:
                        seen.add(y.index)
                        stack.append(y)
            comps.append(comp)
        keep = set(max(comps, key=len))
        drop = [v for v in bm.verts if v not in keep]
    elif rule == "above_knee":  # shorts cut from straight trousers, a hand above the knee
        mw = obj.matrix_world
        cut = meas["knee_z"] + 0.35 * (meas["hips_z"] - meas["knee_z"])
        drop = [v for v in bm.verts if (mw @ v.co).z < cut]
    else:  # above_belt
        mw = obj.matrix_world
        belt = meas["waist_z"] - 0.35 * (meas["waist_z"] - meas["hips_z"])
        drop = [v for v in bm.verts if (mw @ v.co).z < belt]
    bmesh.ops.delete(bm, geom=drop, context="VERTS")
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return len(drop)


# ---------------- sizing ----------------
def target_dims(sex: str, size: str, fit: str, kind: str) -> dict:
    i = SIZES.index(size.upper())
    c = CHART[sex]
    ease, extra_len = FIT.get(fit, FIT["regular"])
    if kind in TOPS:
        return {"girth_cm": c["chest"][i] + ease, "length_cm": c["top_length"][i] + extra_len}
    return {"girth_cm": c["hips"][i] + max(4, ease * 0.6), "waist_cm": c["waist"][i] + ease * 0.3,
            "length_cm": c["inseam"][i] + extra_len}


def resize(garment, body, sex: str, size: str, fit: str, kind: str, meas: dict, scale_length: bool = True) -> dict:
    """Scale the body-hugging garment to its real size, anchored at the shoulders (tops) or waist (bottoms)."""
    tgt = target_dims(sex, size, fit, kind)
    pts = _evaluated_points(garment)
    top_z = max(p.z for p in pts)
    hem_z = min(p.z for p in pts)
    cx = meas["center_x"]
    if kind in TOPS:
        ref_z, half = meas["chest_z"], meas["shoulder_half"] * 0.95
        anchor_z = min(top_z, meas["neck_z"])
        length_now = (anchor_z - hem_z) * 100
    else:
        ref_z, half = meas["hips_z"], meas["shoulder_half"] * 1.25
        anchor_z = top_z
        length_now = (meas["hips_z"] - hem_z) * 100 + 18  # rough inseam from the hip line
    if kind in TOPS:
        g_now = girth(garment, ref_z, half) * 100
    else:
        g_now = max_girth(garment, meas["hips_z"] - 0.06, meas["waist_z"] - 0.03, half) * 100
    sx = max(0.97, tgt["girth_cm"] / g_now) if g_now else 1.0
    sz = max(0.9, tgt["length_cm"] / length_now) if length_now > 0 else 1.0
    if not scale_length:  # skirts, shorts, dresses keep their own length; a much bigger size hangs a bit lower
        sz = 1.0 + max(0.0, sx - 1.0) * 0.15
    # apply on the mesh (modifiers stay on top)
    cy = sum(p.y for p in pts) / len(pts)
    mw, inv = garment.matrix_world, garment.matrix_world.inverted()
    pivot_z = meas["chest_z"] if kind in TOPS else anchor_z
    upper = max(0.0, anchor_z - pivot_z)  # part above the pivot keeps its length
    lower_now = max(1e-3, (anchor_z - hem_z) - upper)
    sz_low = max(0.6, ((anchor_z - hem_z) * sz - upper) / lower_now)
    arm_start = meas["shoulder_half"] * 0.85
    arms = meas.get("arms", {})
    # how far down its arm each sleeve goes (0 shoulder .. 1 hand): a long sleeve already ends at the wrist, so
    # it is neither lengthened nor slid down (its cuff would pile up on the hand)
    reach = {}
    if kind in ("top", "outerwear"):
        for v in garment.data.vertices:
            p = mw @ v.co
            side = "l" if p.x > cx else "r"
            if side in arms and p.z > meas["waist_z"] and abs(p.x - cx) > arm_start + 0.06:
                a0, b0 = arms[side]
                ab0 = b0 - a0
                t0 = (p - a0).dot(ab0) / ab0.length_squared
                if 0 <= t0 <= 1.1 and (p - (a0 + ab0 * min(1.0, t0))).length < 0.12:
                    reach[side] = max(reach.get(side, 0.0), t0)
    for v in garment.data.vertices:
        p = mw @ v.co
        side = "l" if p.x > cx else "r"
        arm = 0.0
        if kind in ("top", "outerwear") and side in arms and p.z > meas["waist_z"]:
            a0, b0 = arms[side]
            ab0 = b0 - a0
            t0 = max(0.0, min(1.0, (p - a0).dot(ab0) / ab0.length_squared))
            near_arm = (p - (a0 + ab0 * t0)).length < 0.12  # only what wraps an arm is a sleeve
            if near_arm:
                arm = min(1.0, max(0.0, (abs(p.x - cx) - arm_start) / 0.06))  # 0 = body of the garment, 1 = sleeve
        # body of the garment: wider around the body's vertical axis; longer only below the pivot (the chest for
        # tops: shoulders and armpits of a longer t-shirt stay where they are, the extra length is lower down)
        q_body = Vector((cx + (p.x - cx) * sx, cy + (p.y - cy) * sx, p.z))
        if p.z < pivot_z:
            q_body.z = pivot_z - (pivot_z - p.z) * sz_low
        q = q_body
        if arm > 0:
            # sleeve: wider around its own arm, and slid down the arm (dropped shoulder of a bigger size)
            a, b = arms[side]  # shoulder -> wrist
            ab = b - a
            t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
            axis = a + ab * t
            radial = p - axis
            drop = ab.normalized() * (meas["shoulder_half"] * (sx - 1) * 0.6)
            sleeve_len = 1 + (sz - 1) * 0.25
            r_side = reach.get(side, 0.0)
            if r_side > 0.7:  # long sleeve: the shoulder drops, the cuff stays at the wrist
                drop = drop * max(0.0, 1.0 - t / r_side)
                sleeve_len = 1.0
            q_sleeve = a + ab * (t * sleeve_len) + drop + radial * sx
            q = q_body.lerp(q_sleeve, arm)
        v.co = inv @ q
    garment.data.update()
    return {"target": tgt, "garment_girth_before_cm": round(g_now, 1), "scale_width": round(sx, 3),
            "scale_length": round(sz, 3), "length_before_cm": round(length_now, 1),
            "sleeve_reach": {k: round(v, 2) for k, v in reach.items()}}


# ---------------- fabric + gravity ----------------
def fabric(gsm: float) -> dict:
    """Grammage (g/m2) -> Blender cloth settings. Light jersey ~120, tee ~160, shirt ~120, jeans ~380,
    sweatshirt ~320, coat ~500."""
    g = max(60.0, min(600.0, gsm))
    t = (g - 60) / 540
    # woven / knitted fabrics barely stretch under their own weight: high tension even for light fabrics
    return {"mass": 0.15 + 0.6 * t, "tension": 18 + 30 * t, "bending": 0.1 + 4.0 * t ** 1.5, "air": 1.0}


def fix_normals(garment) -> None:
    """Make every face point outward (dark creases = faces turned inward after a big deformation)."""
    bm = bmesh.new()
    bm.from_mesh(garment.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(garment.data)
    bm.free()
    garment.data.update()


def weld_seams(garment, dist: float = 0.0015) -> int:
    """Merge vertices sitting at the same place (unstitched seams of the template). Safe on a garment after it
    was fitted (only the BODY must keep its vertices: clothes are bound to it by index)."""
    bm = bmesh.new()
    bm.from_mesh(garment.data)
    n = len(bm.verts)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    merged = n - len(bm.verts)
    bm.to_mesh(garment.data)
    bm.free()
    garment.data.update()
    return merged


def _islands(obj) -> list[set[int]]:
    """Connected pieces of a mesh, as sets of vertex indices."""
    adj = [[] for _ in obj.data.vertices]
    for e in obj.data.edges:
        a, b = e.vertices
        adj[a].append(b)
        adj[b].append(a)
    seen, out = [False] * len(adj), []
    for s0 in range(len(adj)):
        if seen[s0]:
            continue
        stack, comp = [s0], set()
        seen[s0] = True
        while stack:
            x = stack.pop()
            comp.add(x)
            for y in adj[x]:
                if not seen[y]:
                    seen[y] = True
                    stack.append(y)
        out.append(comp)
    return out


def _tighten_under(under, body, above_z: float, offset: float = 0.0015, below_z: float = 1e9) -> None:
    """Press the part of an inner garment that ends up under an outer one (a waistband under a t-shirt)
    against the body, so the outer garment can fall over it without the inner one showing through."""
    mw = under.matrix_world
    fade = 0.03  # the press fades out over 3 cm below the edge: no step, nothing poking through the hem
    vg = under.vertex_groups.get("under_outer") or under.vertex_groups.new(name="under_outer")
    n = 0
    for i, v in enumerate(under.data.vertices):
        z = (mw @ v.co).z
        if z >= below_z or z <= above_z - fade:
            continue
        w = 1.0 if z >= above_z else (z - (above_z - fade)) / fade
        vg.add([i], w * w * (3 - 2 * w), "REPLACE")
        n += 1
    if not n:
        return
    sw = under.modifiers.new("tighten", "SHRINKWRAP")
    sw.target, sw.wrap_method, sw.wrap_mode = body, "NEAREST_SURFACEPOINT", "ON_SURFACE"
    sw.offset, sw.vertex_group = offset, vg.name
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = under
    under.select_set(True)
    bpy.ops.object.modifier_apply(modifier=sw.name)


def drape(garment, body, gsm: float, frames: int = 24, pin_band_cm: float = 3.0, kind: str = "top",
          under: list | None = None, trunk=None) -> dict:
    """Let the garment fall onto the body: body (+ garments already worn under it) = colliders,
    garment = cloth pinned along its top band."""
    import time

    t0 = time.time()
    if not any(m.type == "COLLISION" for m in body.modifiers):
        body.modifiers.new("collision", "COLLISION")
        body.collision.thickness_outer = 0.004
        body.collision.cloth_friction = 8
    hem_z = min((garment.matrix_world @ v.co).z for v in garment.data.vertices)
    for o in under or []:  # e.g. the trousers under a long t-shirt
        # the part under this garment is pressed onto the body (1.5 mm) and this garment stays >= 4 mm off the
        # body, so they never cross. Inner garments are NOT cloth colliders: starting millimetres from a
        # layered waistband (tiered skirt) the solver shreds the hem (tested).
        _tighten_under(o, trunk or body, above_z=hem_z - 0.005)
    # unstitched seams (front / back at the same place) would open in the sim; the static dress fit does not
    # simulate, and welding its bust darts leaves dark creases, so it keeps its seams
    welded = weld_seams(garment) if kind != "dress" else 0
    # pin group: the top band (collar / waistband) holds the garment like shoulders or a belt
    pts = [garment.matrix_world @ v.co for v in garment.data.vertices]
    top_z = max(p.z for p in pts)
    pin = garment.vertex_groups.get("pin") or garment.vertex_groups.new(name="pin")
    # how much of the top rests on the body: collar for tops, waistband for bottoms, straps + chest for dresses
    band = pin_band_cm / 100 * {"top": 0.6, "outerwear": 0.8, "dress": 3.5}.get(kind, 1.0)
    pinned = {i for i, p in enumerate(pts) if p.z > top_z - band}
    # loose pieces not connected to the pinned band (a hem, a frill, a pocket) would fall: hold them in place
    for comp in _islands(garment):
        if not pinned.intersection(comp):
            pinned.update(comp)
    # graded hold: full at the collar / waistband, fading to 0.25 at the bottom of the band (no hard crease)
    for i in sorted(pinned):
        t = (top_z - pts[i].z) / band if band > 0 else 0.0
        pin.add([i], 1.0 if t <= 0.4 else max(0.25, 1.0 - (t - 0.4) * 1.25), "REPLACE")
    if kind in ("top", "outerwear"):
        # the top of a (too big) top rests on the shoulders instead of floating. Not for strappy dresses:
        # their band reaches the bust and pressing it there tears the mesh (tested)
        rest = garment.vertex_groups.get("rest") or garment.vertex_groups.new(name="rest")
        for i in sorted(pinned):
            t = (top_z - pts[i].z) / band if band > 0 else 0.0
            if t < 0.35:  # shoulders / straps / collar only: pressing the chest digs the fabric between breasts
                rest.add([i], (1.0 - t / 0.35) ** 1.5, "REPLACE")
        rs = garment.modifiers.new("rest_on_body", "SHRINKWRAP")
        rs.target, rs.wrap_method, rs.wrap_mode = body, "NEAREST_SURFACEPOINT", "ON_SURFACE"
        rs.offset, rs.vertex_group = 0.006, rest.name
    # push out what is inside the body before simulating
    # push out of the BODY only (closed mesh). Never shrinkwrap "outside" an open garment mesh: inside / outside
    # is undefined there and vertices fly away. Layers under the garment are handled as cloth colliders.
    if kind != "dress":  # a resized strappy dress is bigger than the body; pushing its under-bust "out" snaps it
        # onto the breasts and tears the darts (tested), so dresses skip this step
        sw = garment.modifiers.new("outside", "SHRINKWRAP")
        sw.target, sw.wrap_method, sw.wrap_mode, sw.offset = body, "NEAREST_SURFACEPOINT", "OUTSIDE", 0.004
    if kind == "dress":
        # strappy dresses held by two thin straps collapse at the neckline in the sim (tested): geometric fit
        # instead = real size + straps resting on the shoulders + never inside the body
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = garment
        garment.select_set(True)
        for m in list(garment.modifiers):
            bpy.ops.object.modifier_apply(modifier=m.name)
        fix_normals(garment)
        return {"fabric": fabric(gsm), "frames": 0, "welded_vertices": welded, "mode": "static fit",
                "seconds": round(time.time() - t0, 1)}
    cloth = garment.modifiers.new("cloth", "CLOTH")
    f = fabric(gsm)
    s = cloth.settings
    s.quality, s.mass, s.air_damping = 5, f["mass"], f["air"]
    s.tension_stiffness = s.compression_stiffness = s.shear_stiffness = f["tension"]
    s.bending_stiffness = f["bending"]
    s.vertex_group_mass = "pin"
    cs = cloth.collision_settings
    cs.distance_min, cs.use_self_collision = 0.004, False
    cloth.point_cache.frame_start, cloth.point_cache.frame_end = 1, frames
    sc = bpy.context.scene
    for fr in range(1, frames + 1):
        sc.frame_set(fr)
    # freeze the result into the mesh
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = garment
    garment.select_set(True)
    for m in list(garment.modifiers):  # bake every garment modifier, in stack order
        bpy.ops.object.modifier_apply(modifier=m.name)
    sc.frame_set(1)
    return {"fabric": f, "frames": frames, "welded_vertices": welded, "seconds": round(time.time() - t0, 1)}


# ---------------- ease: fabric hangs, it does not hug ----------------
FIT_LOOSE = {"slim": 0.1, "regular": 0.35, "relaxed": 0.6, "oversize": 0.85}


def looseness(fit: str, scale_width: float | None, gsm: float | None) -> float:
    """0 = follows the body, 1 = falls straight down. A bigger size than the body or a heavier fabric hangs more."""
    v = FIT_LOOSE.get(fit or "regular", 0.45) + max(0.0, (scale_width or 1.0) - 1.0) * 1.0
    if gsm and gsm > 250:
        v += 0.1
    return max(0.0, min(1.0, v))


def _smooth01(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def _profile(pts, centre, nbins: int = 48):
    """Max radius around `centre` per angle bin (empty bins filled from their neighbours, circularly)."""
    import math

    r = [0.0] * nbins
    for p in pts:
        dx, dy = p[0] - centre[0], p[1] - centre[1]
        b = int((math.atan2(dy, dx) + math.pi) / (2 * math.pi) * nbins) % nbins
        r[b] = max(r[b], math.hypot(dx, dy))
    filled = [i for i in range(nbins) if r[i] > 0]
    if not filled:
        return None
    out = r[:]
    for i in range(nbins):
        if out[i] == 0:
            a = max((j for j in filled if j < i), default=filled[-1] - nbins)
            b = min((j for j in filled if j > i), default=filled[0] + nbins)
            t = (i - a) / (b - a)
            out[i] = r[a % nbins] * (1 - t) + r[b % nbins] * t
    return out


def _at(profile, ang: float) -> float:
    import math

    n = len(profile)
    f = (ang + math.pi) / (2 * math.pi) * n - 0.5
    i = int(math.floor(f)) % n
    t = f - math.floor(f)
    return profile[i] * (1 - t) + profile[(i + 1) % n] * t


def hang(garment, meas: dict, kind: str, loose: float, trunk=None) -> dict:
    """Give the garment its air: real fabric falls from where it rests (chest and shoulder blades for a top,
    seat and thigh for trousers) instead of following the waist, the small of the back or the knee.
    Tops: below the chest every vertex moves out towards the outline of the chest section (same angle),
    gradually over 8 cm. Trousers: below the crotch each leg moves out towards its thigh section, slightly
    tapered, the cuff band kept. Soft vertical folds where the fabric stands off. Only ever moves fabric
    OUTWARD (no new contact with the body)."""
    import math

    if loose <= 0.01 or kind in ("shoes", "dress"):
        return {"hang": 0.0}
    mw, inv = garment.matrix_world, garment.matrix_world.inverted()
    pts = [mw @ v.co for v in garment.data.vertices]
    cx = meas["center_x"]
    moved = 0
    if kind in ("top", "outerwear"):
        chest = meas["chest_z"]
        # torso width from the BODY (arm-less trunk), not from the garment: in the A-pose long sleeves come down
        # to the hips, and counting them as torso made "wings" between the arms and the body
        src = trunk if trunk is not None else None
        if src is not None:
            tw = src.matrix_world
            band_b = [abs((tw @ v.co).x - cx) for v in src.data.vertices if abs((tw @ v.co).z - chest) < 0.03]
            torso_half = (max(band_b) if band_b else meas["shoulder_half"]) * 1.12
        else:
            torso_half = meas["shoulder_half"] * 0.9
        arms = list(meas.get("arms", {}).values())

        def on_sleeve(p):  # what wraps an arm is a sleeve, not the body of the garment
            for a0, b0 in arms:
                ab = b0 - a0
                t = (p - a0).dot(ab) / ab.length_squared
                if 0.05 <= t <= 1.2 and (p - (a0 + ab * min(1.0, t))).length < 0.11:
                    return True
            return False

        def arm_dist(p):
            best = 1.0
            for a0, b0 in arms:
                ab = b0 - a0
                t = max(0.0, min(1.0, (p - a0).dot(ab) / ab.length_squared))
                best = min(best, (p - (a0 + ab * t)).length)
            return best

        band = [(p.x, p.y) for p in pts if chest - 0.03 < p.z < chest + 0.01 and abs(p.x - cx) < torso_half
                and not on_sleeve(p)]
        if len(band) < 12:
            return {"hang": 0.0}
        centre = (cx, sum(b[1] for b in band) / len(band))
        prof = _profile(band, centre)
        # never more than 3.5 cm of air beyond the body itself (a wide shoulder seam must not make wings)
        if trunk is not None:
            tw = trunk.matrix_world
            body_band = [((tw @ v.co).x, (tw @ v.co).y) for v in trunk.data.vertices
                         if abs((tw @ v.co).z - chest) < 0.02 and abs((tw @ v.co).x - cx) < torso_half]
            bprof = _profile(body_band, centre) if len(body_band) > 12 else None
            if bprof:
                prof = [min(r, b + 0.035) for r, b in zip(prof, bprof)]
        sel = [(v, p) for v, p in zip(garment.data.vertices, pts)
               if p.z < chest and abs(p.x - cx) <= torso_half and not on_sleeve(p)]
        # outermost radius per (angle, 1 cm) cell: every layer at that spot (lining, double hem) gets the SAME
        # move, so an inner layer never ends up through the outer one
        nb = 48
        cell = {}
        for v, p in sel:
            dx, dy = p.x - centre[0], p.y - centre[1]
            key = (int((math.atan2(dy, dx) + math.pi) / (2 * math.pi) * nb) % nb, int(p.z / 0.01))
            cell[key] = max(cell.get(key, 0.0), math.hypot(dx, dy))
        for v, p in sel:
            dx, dy = p.x - centre[0], p.y - centre[1]
            r = math.hypot(dx, dy)
            if r < 1e-4:
                continue
            ang = math.atan2(dy, dx)
            r_out = cell[(int((ang + math.pi) / (2 * math.pi) * nb) % nb, int(p.z / 0.01))]
            gap = max(0.0, _at(prof, ang) - r_out)
            if gap <= 0:
                continue
            # fades out near the arms: the side under a sleeve stays with the sleeve (no fin between them)
            # front and back fall from the bust / shoulder blades; the sides keep the garment's own seam line
            # (pushing them out made bulges under the arms)
            w = (_smooth01((chest - p.z) / 0.08) * loose * _smooth01((arm_dist(p) - 0.10) / 0.16)
                 * math.sin(ang) ** 2)
            fold = 1.0 + 0.35 * math.sin(ang * 9.0 + 1.3) * _smooth01((chest - 0.06 - p.z) / 0.15)
            nr = r + gap * w * fold
            v.co = inv @ Vector((centre[0] + dx / r * nr, centre[1] + dy / r * nr, p.z))
            moved += 1
    elif kind == "bottom":
        centre_z = [p.z for p in pts if abs(p.x - cx) < 0.012]
        crotch = min(centre_z) if centre_z else meas["hips_z"] - 0.1
        for side in (-1, 1):
            leg = [(i, p) for i, p in enumerate(pts) if p.z < crotch and (p.x - cx) * side > 0]
            if len(leg) < 12:
                continue
            hem = min(p.z for _, p in leg)
            # leg centre per height (legs stand apart in the A-pose): straight line from thigh to hem centres
            def centre_at(z0, half=0.02, leg=leg):
                ring = [p for _, p in leg if abs(p.z - z0) < half]
                return (sum(p.x for p in ring) / len(ring), sum(p.y for p in ring) / len(ring)) if ring else None
            top_z = crotch - 0.04
            c_top, c_bot = centre_at(top_z), centre_at(hem + 0.03)
            if not c_top or not c_bot:
                continue
            ring = [(p.x, p.y) for _, p in leg if abs(p.z - top_z) < 0.02]
            prof = _profile(ring, c_top)
            if prof is None:
                continue
            span = max(1e-3, top_z - hem)

            def leg_centre(z, c_top=c_top, c_bot=c_bot, top_z=top_z, span=span):
                t = (top_z - z) / span
                return t, (c_top[0] + (c_bot[0] - c_top[0]) * t, c_top[1] + (c_bot[1] - c_top[1]) * t)

            nb = 36
            cell = {}  # outermost radius per (angle, 1 cm): all layers move together
            for i, p in leg:
                if p.z <= top_z:
                    _, c = leg_centre(p.z)
                    key = (int((math.atan2(p.y - c[1], p.x - c[0]) + math.pi) / (2 * math.pi) * nb) % nb,
                           int(p.z / 0.01))
                    cell[key] = max(cell.get(key, 0.0), math.hypot(p.x - c[0], p.y - c[1]))
            for i, p in leg:
                if p.z > top_z:
                    continue
                t, c = leg_centre(p.z)  # t: 0 at the thigh, 1 at the hem
                # long, gentle start (the seat above is pressed on the body: a short ramp made a step on the
                # thighs) and less air on the sides of the leg than at the front / back
                w = _smooth01((top_z - p.z) / 0.25) * _smooth01((p.z - hem) / 0.07) * loose
                dx, dy = p.x - c[0], p.y - c[1]
                r = math.hypot(dx, dy)
                if r < 1e-4:
                    continue
                ang = math.atan2(dy, dx)
                target = _at(prof, ang) * (1.0 - 0.22 * t)  # a little narrower towards the ankle
                w *= 0.35 + 0.65 * math.sin(ang) ** 2
                r_out = cell[(int((ang + math.pi) / (2 * math.pi) * nb) % nb, int(p.z / 0.01))]
                gap = max(0.0, target - r_out)
                if gap <= 0:
                    continue
                fold = 1.0 + 0.3 * math.sin(ang * 6.0 + 0.7 + 4.0 * t)
                nr = r + gap * w * fold
                garment.data.vertices[i].co = inv @ Vector((c[0] + dx / r * nr, c[1] + dy / r * nr, p.z))
                moved += 1
    garment.data.update()
    return {"hang": round(loose, 2), "hang_vertices": moved}


# ---------------- layer order: every garment at its own distance from the body ----------------
def _nearest(tree, collider, p):
    hit = tree.find_nearest(collider.matrix_world.inverted() @ p)
    if hit[0] is None:
        return None
    q = collider.matrix_world @ hit[0]
    n = (collider.matrix_world.to_3x3() @ hit[1]).normalized()
    return q, n, (p - q).dot(n)


def _spot(q) -> tuple:
    return (round(q.x / 0.015), round(q.y / 0.015), round(q.z / 0.015))


def bottom_envelope(z: float, meas: dict) -> float:
    """Farthest a trouser / skirt may stand off the body at height z: 4 mm at the waist, growing smoothly to
    15 mm at the crotch and then quickly free down the thigh. A smooth limit (instead of pressing the seat flat
    down to the crotch) leaves no ledge on the thighs; tops are laid just outside it."""
    top = meas["hips_z"] - 0.04
    crotch = meas["hips_z"] - 0.08
    if z >= top:
        return 0.004
    if z >= crotch:
        return 0.004 + 0.011 * _smooth01((top - z) / max(1e-3, top - crotch))
    return 0.015 + 0.6 * (crotch - z)


def _need(kind: str, z: float, meas: dict) -> float:
    cover_z = meas["waist_z"] + 0.05  # below this a top lies over trousers
    if kind == "top":
        over = min(0.05, bottom_envelope(z, meas) + 0.007)  # just outside where trousers can be
        return 0.008 + max(0.0, over - 0.008) * _smooth01((cover_z - z) / 0.05)
    if kind == "outerwear":
        return 0.020 + 0.006 * _smooth01((cover_z - z) / 0.05)
    return {"shoes": 0.002, "bottom": 0.004, "dress": 0.006}.get(kind, 0.006)


def min_offset(garment, collider, meas: dict, kind: str) -> dict:
    """Push the garment out to its layer's distance from the body (trousers 4 mm, tops >= 8 mm and >= 14 mm
    where they can cover trousers, jackets >= 20 mm): garments are fitted one by one, this guarantees the
    stacking. The push is decided per body spot (1.5 cm cell of the nearest body point) from the innermost layer
    there and applied to EVERY layer at that spot, so double layers keep their order (no lining pushed onto or
    through the outer fabric)."""
    from mathutils.bvhtree import BVHTree

    if kind == "shoes":
        return {"min_offset_moved": 0}
    tree = BVHTree.FromObject(collider, bpy.context.evaluated_depsgraph_get())
    mw, inv = garment.matrix_world, garment.matrix_world.inverted()
    info, push = [], {}
    for v in garment.data.vertices:
        p = mw @ v.co
        h = _nearest(tree, collider, p)
        if h is None:
            info.append(None)
            continue
        q, n, d = h
        key = _spot(q)
        info.append((p, n, key))
        need = _need(kind, p.z, meas)
        if d < need:
            push[key] = max(push.get(key, 0.0), need - d)
    moved = 0
    for v, it in zip(garment.data.vertices, info):
        if it and push.get(it[2], 0.0) > 0:
            v.co = inv @ (it[0] + it[1] * push[it[2]])
            moved += 1
    garment.data.update()
    return {"min_offset_moved": moved}


def densify(garment, max_edge: float = 0.02, rounds: int = 2) -> int:
    """Split edges longer than `max_edge` (UVs interpolated). A coarse garment can have every vertex outside the
    body and still cut through it with its flat faces where the body is curved (hips, seat, crotch); smaller
    faces follow the body, and min_offset then keeps all of them outside."""
    mw = garment.matrix_world
    added = 0
    for _ in range(rounds):
        bm = bmesh.new()
        bm.from_mesh(garment.data)
        long_edges = [e for e in bm.edges if ((mw @ e.verts[0].co) - (mw @ e.verts[1].co)).length > max_edge]
        if not long_edges:
            bm.free()
            break
        n0 = len(bm.verts)
        bmesh.ops.subdivide_edges(bm, edges=long_edges, cuts=1, use_grid_fill=True)
        added += len(bm.verts) - n0
        bm.to_mesh(garment.data)
        bm.free()
    garment.data.update()
    return added


LAYER_NEED = {"shoes": 0.002, "bottom": 0.004, "dress": 0.006, "top": 0.008, "outerwear": 0.02}


def resolve_crossings(garment, collider, kind: str, rounds: int = 10) -> dict:
    """Last pass: points spread over every face (centre, edge middles, half-way to the corners) are tested
    against the body; a face with a point under the skin (closer than its layer allows) has its vertices pushed
    out along the body normal there. Repeated until no face crosses (or `rounds`). Catches what vertex-only
    checks miss: legs through a long skirt hem, toes through a shoe, an elbow through a sleeve."""
    from mathutils.bvhtree import BVHTree

    need = LAYER_NEED.get(kind, 0.006)
    dg = bpy.context.evaluated_depsgraph_get()
    tree = BVHTree.FromObject(collider, dg)
    cmw, cinv, crot = collider.matrix_world, collider.matrix_world.inverted(), collider.matrix_world.to_3x3()
    mw, inv = garment.matrix_world, garment.matrix_world.inverted()
    me = garment.data
    history = []
    for _ in range(rounds):
        vs = [mw @ v.co for v in me.vertices]
        push = {}
        crossing = 0
        for poly in me.polygons:
            idx = list(poly.vertices)
            pts = [vs[k] for k in idx]
            c = sum(pts, Vector()) / len(pts)
            samples = [c] + [(pts[k] + pts[(k + 1) % len(pts)]) / 2 for k in range(len(pts))] + [(c + q) / 2 for q in pts]
            worst = None
            for sp in samples:
                hit = tree.find_nearest(cinv @ sp)
                if hit[0] is None:
                    continue
                q, n = cmw @ hit[0], (crot @ hit[1]).normalized()
                d = (sp - q).dot(n)
                if d < need and (worst is None or d < worst[0]):
                    worst = (d, n)
            if worst is None:
                continue
            crossing += 1
            vec = worst[1] * min(0.015, need - worst[0] + 0.001)  # small steps: no spikes where a hand meets a cuff
            for k in idx:
                if k not in push or vec.length > push[k].length:
                    push[k] = vec
        history.append(crossing)
        if not crossing:
            break
        for k, vec in push.items():
            me.vertices[k].co = inv @ (vs[k] + vec)
        me.update()
    return {"crossings": history}


def orient_outward(garment, collider) -> int:
    """Turn every face so it looks away from the body. Templates (and folds made by resizing / draping) leave
    some faces pointing inwards: lit from the wrong side they render as dark patches, and the photo projection
    uses face directions for front / back. A face of an inner lining is hidden anyway, so flipping it is safe."""
    from mathutils.bvhtree import BVHTree

    tree = BVHTree.FromObject(collider, bpy.context.evaluated_depsgraph_get())
    cinv = collider.matrix_world.inverted()
    mw = garment.matrix_world
    rot = mw.to_3x3()
    bm = bmesh.new()
    bm.from_mesh(garment.data)
    flipped = 0
    for f in bm.faces:
        c = mw @ f.calc_center_median()
        hit = tree.find_nearest(cinv @ c)
        if hit[0] is None:
            continue
        q = collider.matrix_world @ hit[0]
        if (c - q).dot((rot @ f.normal).normalized()) < 0:
            f.normal_flip()
            flipped += 1
    bm.to_mesh(garment.data)
    bm.free()
    garment.data.update()
    return flipped


def max_offset(garment, collider, meas: dict) -> dict:
    """Trousers / skirts: pull every vertex farther from the body than bottom_envelope(z) in to that distance
    (along the body normal at the nearest point). Graded with height, so no step."""
    from mathutils.bvhtree import BVHTree

    tree = BVHTree.FromObject(collider, bpy.context.evaluated_depsgraph_get())
    mw, inv = garment.matrix_world, garment.matrix_world.inverted()
    moved = 0
    for v in garment.data.vertices:
        p = mw @ v.co
        lim = bottom_envelope(p.z, meas)
        if lim > 0.08:
            continue
        h = _nearest(tree, collider, p)
        if h is None:
            continue
        q, n, d = h
        if d > lim:
            v.co = inv @ (p - n * (d - lim))
            moved += 1
    garment.data.update()
    return {"max_offset_moved": moved}
