"""Cloth physics for the try-on (Blender cloth solver). Runs inside Blender.

1. settle(): one garment falls onto what is under it (gravity, its fabric, collisions), held where it really
   rests (shoulders / collar for a top, waistband for trousers): natural folds, never through the body.
2. build_outfit(): a combination worn together. Garments are stacked from the inside out; each one is first
   lifted just outside the layers under it, then settles ONTO them (trousers and body are obstacles for the
   shirt). Every garment is exported again as its own GLB, so the viewer swaps them in.
3. Animation (build_outfit with "animate"): the avatar turns on the spot while every garment is simulated as
   cloth; the motion (inertia, swing, settling) is baked into morph targets, one per sampled frame. The
   viewer turns the avatar with the same curve (turn_angle) and blends the morph targets.

No model is trained; this is the physics solver of Blender.
"""

from __future__ import annotations

import json
import math
import os
import sys
import time

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import garment_fit  # noqa: E402

LAYER = {"shoes": 0, "bottom": 1, "dress": 2, "top": 3, "outerwear": 4}
GSM = {"shoes": 0, "bottom": 300, "dress": 160, "top": 170, "outerwear": 350}
FPS = 30
TURN = {"settle": 12, "turn": 60, "after": 36, "step": 3}  # frames: still, turning 360 degrees, swinging back
MEMORY = 0.12  # soft pull of every cloth point towards its resting place during the animation


def turn_angle(frame: float) -> float:
    """Avatar rotation (radians) at a frame; the viewer uses the same curve."""
    f0, f1 = TURN["settle"], TURN["settle"] + TURN["turn"]
    if frame <= f0:
        return 0.0
    if frame >= f1:
        return 2 * math.pi
    t = (frame - f0) / (f1 - f0)
    return 2 * math.pi * t * t * (3 - 2 * t)


# ---------------- helpers ----------------
def _select_only(obj) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _apply_all(obj) -> None:
    _select_only(obj)
    for m in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


def add_collider(obj, thickness: float = 0.003) -> None:
    if not any(m.type == "COLLISION" for m in obj.modifiers):
        obj.modifiers.new("collision", "COLLISION")
    obj.collision.thickness_outer = thickness
    obj.collision.thickness_inner = 0.002
    obj.collision.cloth_friction = 2.5  # fabric slides on fabric (a shirt must not ride up on trousers)
    obj.collision.damping = 0.6


def remove_collider(obj) -> None:
    for m in [m for m in obj.modifiers if m.type == "COLLISION"]:
        obj.modifiers.remove(m)


def pin_group(garment, kind: str):
    """Where the garment hangs from: collar / shoulders for tops, waistband for trousers and skirts, straps for
    dresses. Graded weights, so there is no hard crease at the edge of the held band."""
    mw = garment.matrix_world
    pts = [mw @ v.co for v in garment.data.vertices]
    top = max(p.z for p in pts)
    band = {"bottom": 0.05, "dress": 0.10, "top": 0.07, "outerwear": 0.08}.get(kind, 0.06)
    g = garment.vertex_groups.get("pin") or garment.vertex_groups.new(name="pin")
    for i, p in enumerate(pts):
        t = (top - p.z) / band
        if t <= 1.0:
            g.add([i], 1.0 if t < 0.5 else 1.0 - (t - 0.5) * 1.6, "REPLACE")
    return g


def push_outside(garment, inner: list, gap: float = 0.006, near: float = 0.06) -> int:
    """Lift every vertex of `garment` that is behind (or closer than `gap` to) an inner layer just outside it,
    along the inner surface normal. A cloth solver cannot untangle a garment that STARTS through another one."""
    if not inner:
        return 0
    dg = bpy.context.evaluated_depsgraph_get()
    trees = [(o, BVHTree.FromObject(o, dg)) for o in inner]
    mw, inv = garment.matrix_world, garment.matrix_world.inverted()
    moved = 0
    for v in garment.data.vertices:
        p = mw @ v.co
        changed = False
        for o, tree in trees:
            oinv = o.matrix_world.inverted()
            hit = tree.find_nearest(oinv @ p, near)
            if hit[0] is None:
                continue
            q = o.matrix_world @ hit[0]
            n = (o.matrix_world.to_3x3() @ hit[1]).normalized()
            d = (p - q).dot(n)
            if d < gap:
                p = q + n * gap
                changed = True
        if changed:
            v.co = inv @ p
            moved += 1
    garment.data.update()
    return moved


def add_cloth(garment, kind: str, gsm: float | None, frames: int):
    f = garment_fit.fabric(gsm or GSM.get(kind, 180))
    pin = pin_group(garment, kind)
    cloth = garment.modifiers.new("cloth", "CLOTH")
    s = cloth.settings
    s.quality = 6
    s.mass, s.air_damping = f["mass"], f["air"]
    s.tension_stiffness = s.compression_stiffness = s.shear_stiffness = f["tension"]
    s.bending_stiffness = f["bending"]
    s.vertex_group_mass = pin.name
    s.pin_stiffness = 2.0
    cs = cloth.collision_settings
    cs.collision_quality = 4
    cs.distance_min = 0.004
    cs.use_self_collision = False
    cloth.point_cache.frame_start, cloth.point_cache.frame_end = 1, frames
    return cloth


def settle(garment, obstacles: list, kind: str, gsm: float | None = None, frames: int = 30) -> dict:
    """Let one garment fall onto `obstacles` (body, garments under it) and freeze the result."""
    t0 = time.time()
    for o in obstacles:
        add_collider(o)
    add_cloth(garment, kind, gsm, frames)
    sc = bpy.context.scene
    for fr in range(1, frames + 1):
        sc.frame_set(fr)
    _apply_all(garment)
    sc.frame_set(1)
    return {"frames": frames, "seconds": round(time.time() - t0, 1)}


# ---------------- 2 + 3: a combination worn together ----------------
def _import(path: str):
    before = set(bpy.data.objects)
    # a GLB splits vertices along texture seams: re-stitched on import, otherwise the garment is made of loose
    # pieces and falls apart in the cloth solver (tested)
    bpy.ops.import_scene.gltf(filepath=path, merge_vertices=True)
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    obj = meshes[0]
    if len(meshes) > 1:  # several primitives -> one object
        _select_only(obj)
        for m in meshes[1:]:
            m.select_set(True)
        bpy.ops.object.join()
    for o in new:  # glTF import adds parents / empties: keep the mesh, in world space
        if o.type != "MESH" and o.name in bpy.data.objects:
            for c in o.children:
                mw = c.matrix_world.copy()
                c.parent = None
                c.matrix_world = mw
    for o in [o for o in new if o.name in bpy.data.objects and o.type != "MESH"]:
        bpy.data.objects.remove(o, do_unlink=True)
    _select_only(obj)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    garment_fit.weld_seams(obj, dist=0.0005)  # same position, different normals -> one vertex
    return obj


def _export(obj, path: str, morphs: bool = False) -> None:
    _select_only(obj)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=not morphs,
                              export_yup=True, export_image_format="JPEG", export_jpeg_quality=88,
                              export_morph=morphs, export_morph_normal=False, export_animations=False)


def build_outfit(spec: dict) -> dict:
    """spec = {"body": body.glb, "pieces": [{"id", "glb", "kind", "gsm"?}], "out_dir",
               "animate": bool}  -> out_dir/<id>.glb (worn together) [+ out_dir/anim/<id>.glb + anim.json]"""
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = FPS
    body = _import(spec["body"])
    body.name = "body"
    pieces = sorted(spec["pieces"], key=lambda p: LAYER.get(p.get("kind", "top"), 3))
    objs, report = [], {}
    stack = []  # what is already worn, inside -> out (obstacles for the next garment)
    for p in pieces:
        g = _import(p["glb"])
        g.name = f"garment_{p['id']}"
        kind = p.get("kind", "top")
        info = {"kind": kind}
        if kind != "shoes" and stack:
            info["lifted"] = push_outside(g, stack)
            if kind != "dress":  # strappy dresses collapse at the neckline in the solver (tested)
                info.update(settle(g, [body] + stack, kind, p.get("gsm"), frames=24))
                info["lifted_after"] = push_outside(g, stack, gap=0.004)  # the solver's last millimetres
        objs.append((p, g))
        stack.append(g)
        report[p["id"]] = info
    os.makedirs(spec["out_dir"], exist_ok=True)
    for o in [body] + [g for _, g in objs]:
        remove_collider(o)
    for p, g in objs:
        _export(g, os.path.join(spec["out_dir"], f"{p['id']}.glb"))
    result = {"pieces": report, "seconds_static": round(time.time() - t0, 1)}
    if spec.get("animate"):
        result["animation"] = _animate(body, objs, spec["out_dir"])
    result["seconds"] = round(time.time() - t0, 1)
    return result


def animate(body, objs: list, anim_dir: str) -> dict:
    """objs = [(piece {"id", "kind", "gsm"}, object)] already fitted and worn together. anim_dir must end with
    "anim": writes anim_dir/<id>.glb (morph targets) + anim_dir/anim.json."""
    return _animate(body, objs, os.path.dirname(os.path.normpath(anim_dir)))


def _animate(body, objs: list, out_dir: str) -> dict:
    """The avatar turns on the spot; every garment is cloth (held where it rests, colliding with the body and
    the layers under it). Each garment's deformation is sampled every TURN['step'] frames into morph targets
    (local space of the turning avatar, so the viewer only has to turn the whole avatar the same way)."""
    t0 = time.time()
    sc = bpy.context.scene
    total = TURN["settle"] + TURN["turn"] + TURN["after"]
    sc.frame_start, sc.frame_end = 1, total
    pivot = bpy.data.objects.new("pivot", None)
    sc.collection.objects.link(pivot)
    for o in [body] + [g for _, g in objs]:
        o.parent = pivot
    for fr in range(1, total + 1):
        pivot.rotation_euler = (0, 0, turn_angle(fr))
        pivot.keyframe_insert("rotation_euler", frame=fr)
    # contact zone (body thickness + cloth distance = 3 mm) thinner than the closest the garments rest to the
    # body after fitting (4 mm): a cloth that starts inside the zone is shot away and explodes (tested)
    add_collider(body, 0.001)
    cloths, rigid = [], []
    top_layer = max(LAYER.get(p.get("kind", "top"), 3) for p, _ in objs)
    for p, g in objs:
        kind = p.get("kind", "top")
        remove_collider(g)
        if kind == "shoes" or LAYER.get(kind, 3) < top_layer:
            # covered garments (trousers under a shirt) and shoes stay still: a cloth colliding with another
            # garment's thin open surface catches and explodes (tested); the moving outer garment is lifted
            # above them frame by frame instead (below)
            rigid.append(g)
            continue
        if p.get("base_co") and len(p["base_co"]) == len(g.data.vertices):
            for v, co in zip(g.data.vertices, p["base_co"]):  # start from its own shape (stable), layered later
                v.co = co
            g.data.update()
        cloth = add_cloth(g, kind, p.get("gsm"), total)  # collides with the body only (stable: tested)
        cloth.collision_settings.distance_min = 0.002
        cloth.settings.quality = 8
        cloth.collision_settings.collision_quality = 4
        cloth.settings.use_internal_springs = False
        # elastic memory: every point is softly pulled back to where it rests (its pinned target follows the
        # turning avatar), so the fabric swings during the turn and settles back instead of riding up for good
        pin = g.vertex_groups["pin"]
        for v in g.data.vertices:
            w = max((gr.weight for gr in v.groups if gr.group == pin.index), default=0.0)
            if w < MEMORY:
                pin.add([v.index], MEMORY, "REPLACE")
        cloth.settings.pin_stiffness = 1.0
        cloths.append((p, g))
    frames = list(range(1, total + 1, TURN["step"]))
    if frames[-1] != total:
        frames.append(total)
    samples = {p["id"]: [] for p, _ in cloths}
    for fr in range(1, total + 1):
        sc.frame_set(fr)
        if fr in frames:
            dg = bpy.context.evaluated_depsgraph_get()
            for p, g in cloths:
                ev = g.evaluated_get(dg)
                samples[p["id"]].append([v.co.copy() for v in ev.data.vertices])
    # layers: each sampled frame of a moving garment is lifted just outside the garments under it
    sc.frame_set(1)
    for p, g in cloths:
        for m in list(g.modifiers):
            g.modifiers.remove(m)
    lifted = 0
    if rigid:
        for p, g in cloths:
            for cos in samples[p["id"]]:
                for v, co in zip(g.data.vertices, cos):
                    v.co = co
                lifted += push_outside(g, rigid, gap=0.006)
                for k, v in enumerate(g.data.vertices):
                    cos[k] = v.co.copy()
            for v, co in zip(g.data.vertices, samples[p["id"]][0]):
                v.co = co
    anim_dir = os.path.join(out_dir, "anim")
    os.makedirs(anim_dir, exist_ok=True)
    for p, g in cloths:
        frames_co = samples[p["id"]]
        if len(frames_co[0]) != len(g.data.vertices):
            continue
        g.shape_key_add(name="Basis", from_mix=False)
        for k, cos in enumerate(frames_co):
            key = g.shape_key_add(name=f"f{k:03d}", from_mix=False)
            for v, co in zip(key.data, cos):
                v.co = co
        g.parent = None  # export in the avatar's own (unrotated) space
        g.matrix_world = g.matrix_world.copy()
        _export(g, os.path.join(anim_dir, f"{p['id']}.glb"), morphs=True)
    meta = {"fps": FPS, "frames": frames, "total": total, "turn": TURN, "pieces": [p["id"] for p, _ in cloths],
            "rigid": [p["id"] for p, _ in objs if p["id"] not in {q["id"] for q, _ in cloths}], "lifted": lifted, "seconds": round(time.time() - t0, 1)}
    json.dump(meta, open(os.path.join(anim_dir, "anim.json"), "w"))
    return meta


if __name__ == "__main__" and "--" in sys.argv:  # blender -b --python cloth_sim.py -- spec.json
    res = build_outfit(json.load(open(sys.argv[sys.argv.index("--") + 1])))
    print("OUTFIT_RESULT " + json.dumps(res, default=str))
