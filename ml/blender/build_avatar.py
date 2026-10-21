"""Build a faceless dressed avatar in Blender with MPFB and export it as GLB.

Runs INSIDE Blender (MPFB 2 add-on + CC0 MakeHuman asset packs installed). Called through the Blender MCP
bridge or headless:  blender -b --python build_avatar.py -- spec.json

spec = {
  "sex": "female" | "male", "height_cm": 165, "weight_kg": 60,
  "outfit": [{"asset": "toigo_basic_tucked_t-shirt", "color": "#3b6db3"}, ...],   # MPFB clothes names
  "out": "C:/.../avatar.glb", "preview": "C:/.../avatar.png" (optional)
}
or spec["mode"] = "parts": the body and each garment as separate GLBs (see build_parts), for a viewer that
puts garments on and off instantly.
"""

from __future__ import annotations

import json
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import body_fit  # noqa: E402
import cloth_sim  # noqa: E402
import pattern_garment  # noqa: E402
import garment_fit  # noqa: E402
import garment_texture  # noqa: E402
import templates  # noqa: E402

MANNEQUIN_RGB = (0.80, 0.78, 0.75, 1.0)  # matte light grey, like a shop mannequin


def _mpfb():
    from bl_ext.user_default.mpfb.services import HumanService, LocationService, TargetService

    return HumanService, LocationService, TargetService


def clear_scene() -> None:
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for block in list(coll):
            if block.users == 0:
                coll.remove(block)


def _group_center(obj, name: str) -> Vector | None:
    vg = obj.vertex_groups.get(name)
    if vg is None:
        return None
    pts = [obj.matrix_world @ v.co for v in obj.data.vertices if any(g.group == vg.index for g in v.groups)]
    return sum(pts, Vector()) / len(pts) if pts else None


def bake_shape(body) -> None:
    """MPFB shapes the body with shape keys (sex, weight, height...). Merge them into the mesh so later edits
    (the faceless head) are not undone by the keys."""
    if body.data.shape_keys is None:
        return
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = body
    body.select_set(True)
    bpy.ops.object.shape_key_remove(all=True, apply_mix=True)


def make_faceless(body, blend: float = 0.22) -> int:
    """Mannequin head: every vertex above the neck is moved onto a smooth ellipsoid fitted to the head,
    which erases eyes, nose, mouth and ears. A blend zone near the neck keeps the join seamless."""
    neck = _group_center(body, "joint-neck")
    head = _group_center(body, "joint-head")
    if neck is None or head is None:
        return 0
    inv = body.matrix_world.inverted()
    z0 = (inv @ Vector((0, 0, neck.z + 0.12 * (head.z - neck.z)))).z  # where the blend starts (jaw included)
    helpers = body.vertex_groups.get("HelperGeometry")
    bm = bmesh.new()
    bm.from_mesh(body.data)
    deform = bm.verts.layers.deform.verify()
    verts = [v for v in bm.verts if v.co.z > z0 and not (helpers and helpers.index in v[deform])]
    if not verts:
        bm.free()
        return 0
    xs, ys, zs = ([v.co[k] for v in verts] for k in range(3))
    top = max(zs)
    center = Vector(((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, (top + z0) / 2 + 0.12 * (top - z0)))
    rx, ry = 0.40 * (max(xs) - min(xs)), 0.46 * (max(ys) - min(ys))  # ears excluded from the width
    rz = top - center.z
    span = top - z0
    for v in verts:
        d = v.co - center
        n = Vector((d.x / rx, d.y / ry, d.z / rz))
        if n.length < 1e-6:
            continue
        target = center + Vector((d.x, d.y, d.z)) / n.length  # point of the ellipsoid in that direction
        t = min(1.0, (v.co.z - z0) / (blend * span))  # 0 at the bottom of the zone, 1 above it
        t = t * t * (3 - 2 * t)
        v.co = v.co.lerp(target, t)
    # NOTE: never merge/delete vertices here: clothes are bound to the body by vertex index.
    for _ in range(10):  # relax the result
        bmesh.ops.smooth_vert(bm, verts=verts, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    for f in bm.faces:
        f.smooth = True
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    return len(verts)


def make_collider(body):
    """Invisible copy of the whole body (helpers hidden, nothing else) used as the target of every press /
    push / collision. The visible body gets MPFB "Delete.<garment>" masks that cut holes under the clothes."""
    col = body.copy()
    col.data = body.data.copy()
    col.name = "body_collider"
    bpy.context.collection.objects.link(col)
    for m in list(col.modifiers):
        if m.type != "MASK" or "helper" not in m.name.lower():
            col.modifiers.remove(m)
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = col
    col.select_set(True)
    for m in list(col.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)
    col.hide_render = True
    return col


def make_trunk(collider, meas: dict):
    """Copy of the collider without the arms (target for pressing inner garments onto the torso and hips)."""
    import bmesh as _bm

    tr = collider.copy()
    tr.data = collider.data.copy()
    tr.name = "body_trunk"
    bpy.context.collection.objects.link(tr)
    bm = _bm.new()
    bm.from_mesh(tr.data)
    # remove what is around each arm (distance to the shoulder -> hand axis), not everything wider than the
    # shoulders: on a broad body the hips are wider than that and pressing trousers on a hip-less trunk pulled
    # their sides into the body
    mw = tr.matrix_world
    segs = list(meas.get("arms", {}).values())

    def near_arm(p):
        for a, b in segs:
            ab = b - a
            t = (p - a).dot(ab) / ab.length_squared
            if 0.15 <= t <= 1.15 and (p - (a + ab * min(1.0, t))).length < 0.065:
                return True
        return False

    drop = [v for v in bm.verts if near_arm(mw @ v.co)]
    _bm.ops.delete(bm, geom=drop, context="VERTS")
    bm.to_mesh(tr.data)
    bm.free()
    tr.hide_render = True
    return tr


def mannequin_material(body) -> None:
    mat = bpy.data.materials.new("mannequin")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = MANNEQUIN_RGB
    bsdf.inputs["Roughness"].default_value = 0.65
    body.data.materials.clear()
    body.data.materials.append(mat)


def _hex(c: str) -> tuple[float, float, float, float]:
    c = c.lstrip("#")
    srgb = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in srgb]
    return (*lin, 1.0)


def tint(obj, color: str) -> None:
    """Plain colour of the real piece. glTF / GLB can only multiply a texture by a colour (which darkens the
    template's texture), so the colour is set as is: the 3D viewer shows exactly the chosen colour."""
    for slot in obj.material_slots:
        mat = slot.material
        if mat is None or not mat.use_nodes:
            continue
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            continue
        base = bsdf.inputs["Base Color"]
        for link in list(base.links):
            nt.links.remove(link)
        base.default_value = _hex(color)
        bsdf.inputs["Roughness"].default_value = 0.8


def push_off_skin(obj, mm: float) -> None:
    """Move a garment a few millimetres outward along its normals so the body does not poke through."""
    mod = obj.modifiers.new("off_skin", "DISPLACE")
    mod.strength = mm / 1000
    mod.mid_level = 0.0
    mod.direction = "NORMAL"


def build(spec: dict) -> dict:
    HumanService, LocationService, TargetService = _mpfb()
    clear_scene()
    fit = body_fit.fit(spec["sex"], spec["height_cm"], spec["weight_kg"])
    macro = TargetService.get_default_macro_info_dict()
    macro.update(gender=fit["gender"], height=fit["height"], weight=fit["weight"], muscle=fit["muscle"])
    body = HumanService.create_human(macro_detail_dict=macro)
    body.name = "avatar_body"
    bake_shape(body)
    smoothed = make_faceless(body)
    mannequin_material(body)

    data = LocationService.get_user_data()
    pieces, sizing = [], {}
    meas = garment_fit.measure_body(body)
    collider = make_collider(body)  # whole body: MPFB hides the body under each garment, targets must not
    trunk = make_trunk(collider, meas)  # same without the arms: pressing a hem must not snap it to the hands
    layer = {"shoes": 0, "bottom": 1, "dress": 2, "top": 3, "outerwear": 4}
    worn = []  # garments already on the body, in dressing order (inner layers first)
    outfit = []
    for piece in spec.get("outfit", []):
        if piece.get("type") and not piece.get("asset"):  # garment type -> template (+ defaults)
            photo = json.load(open(piece["texture"])) if piece.get("texture") else None
            piece = {**templates.resolve(piece["type"], spec["sex"], photo, piece.get("length"), piece.get("sleeves")), **piece}
        outfit.append(piece)
    for piece in sorted(outfit, key=lambda p: layer.get(p.get("kind", "top"), 3)):
        folder = os.path.join(data, "clothes", piece["asset"])
        mhclo = next(os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".mhclo"))
        obj = HumanService.add_mhclo_asset(mhclo, body, asset_type="Clothes", subdiv_levels=0, set_up_rigging=False,
                                           interpolate_weights=False, import_subrig=False, import_weights=False)
        obj.name = f"garment_{piece.get('type', piece['asset'])}"
        if piece.get("part"):  # only the jacket of a suit, only the shirt of a shirt + jeans outfit
            garment_fit.extract_part(obj, piece["part"], meas)
            mask = body.modifiers.get(f"Delete.{piece['asset']}")  # MPFB hid the body under the WHOLE outfit
            if mask:
                body.modifiers.remove(mask)
        push_off_skin(obj, 4 + 2 * len(pieces))  # outer layers a bit further out
        kind = piece.get("kind", "top")
        if piece.get("color") and not piece.get("texture"):
            tint(obj, piece["color"])
        if piece.get("size") and kind != "shoes":
            info = garment_fit.resize(obj, collider, spec["sex"], piece["size"], piece.get("fit", "regular"), kind, meas,
                                      scale_length=piece.get("scale_length", True))
            if abs(info["scale_width"] - 1) > 0.06 or abs(info["scale_length"] - 1) > 0.06:
                # the size really changes the garment: let it fall onto the body with its fabric
                info["drape"] = garment_fit.drape(obj, collider, piece.get("gsm", 180), kind=kind, trunk=trunk,
                                                  under=[o for o in worn if o.type == "MESH"])
            else:  # close to the template's own fit: keep its clean shape, just stay off what is under it
                lo = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
                hi = max((obj.matrix_world @ v.co).z for v in obj.data.vertices)
                for o in worn:
                    garment_fit._tighten_under(o, trunk, above_z=lo - 0.005, below_z=hi)
                info["drape"] = "skipped (size close to the template)"
            sizing.setdefault(obj.name, {}).update(info)
        elif worn and kind != "shoes":
            # not resized: still press what is under it (shoe tops under trouser hems) against the body
            lo = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
            hi = max((obj.matrix_world @ v.co).z for v in obj.data.vertices)
            for o in worn:
                garment_fit._tighten_under(o, trunk, above_z=lo - 0.02, below_z=hi)
        if piece.get("texture"):
            # photo of the real piece, projected onto the FINAL shape (after resizing / draping) so the print is
            # not distorted; it still grows with a bigger size because the projection follows the garment
            sizing.setdefault(obj.name, {})["texture"] = garment_texture.apply(obj, meas, piece["texture"], kind)
        pieces.append(obj.name)
        worn.append(obj)

    bpy.data.objects.remove(collider, do_unlink=True)
    bpy.data.objects.remove(trunk, do_unlink=True)
    if spec.get("out"):
        bpy.ops.object.select_all(action="DESELECT")
        for o in bpy.data.objects:
            if o.type == "MESH":
                o.select_set(True)
        bpy.ops.export_scene.gltf(filepath=spec["out"], export_format="GLB", use_selection=True,
                                  export_apply=True, export_yup=True)
    if spec.get("preview"):
        render_preview(spec["preview"])
    return {"fit": fit, "body": {k: v for k, v in meas.items() if k.endswith("_cm")}, "garments": pieces,
            "sizing": sizing, "faceless_vertices": smoothed, "glb": spec.get("out")}


def make_opaque(obj) -> None:
    """Garments are solid fabric. MakeHuman materials carry an alpha channel (and Blender's blend mode), which glTF
    exports as alphaMode BLEND: transparent surfaces are drawn in a jumbled order (pixelated dark stripes) and
    fully transparent texels show the body through the fabric (holes)."""
    for slot in obj.material_slots:
        mat = slot.material
        if mat is None:
            continue
        if hasattr(mat, "surface_render_method"):
            mat.surface_render_method = "DITHERED"
        if hasattr(mat, "blend_method"):
            try:
                mat.blend_method = "OPAQUE"
            except TypeError:
                pass
        if mat.use_nodes:
            for n in mat.node_tree.nodes:
                if n.type == "BSDF_PRINCIPLED":
                    a = n.inputs["Alpha"]
                    for link in list(a.links):
                        mat.node_tree.links.remove(link)
                    a.default_value = 1.0


# separate garments: each one is fitted alone on the body and lies at its own distance from the skin, so the
# viewer can put any combination on and off without a new render (outer layers further out)
LAYER_MM = {"shoes": 2, "bottom": 4, "dress": 6, "top": 9, "outerwear": 15}


def _export_one(obj, path: str) -> None:
    mw = obj.matrix_world.copy()
    obj.parent = None
    obj.matrix_world = mw
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True, export_apply=True,
                              export_yup=True, export_image_format="JPEG", export_jpeg_quality=88)


def build_parts(spec: dict) -> dict:
    """spec = {sex, height_cm, weight_kg, "body_out": glb path or None,
               "pieces": [{"id", "out": glb path, "type" | "asset", size, fit, gsm, length, sleeves,
                           "texture" | "color"}]}
    -> the faceless body alone (no garment masks) + one GLB per garment, all in the same space. A failing piece
    does not stop the others."""
    HumanService, LocationService, TargetService = _mpfb()
    clear_scene()
    fit = body_fit.fit(spec["sex"], spec["height_cm"], spec["weight_kg"])
    macro = TargetService.get_default_macro_info_dict()
    macro.update(gender=fit["gender"], height=fit["height"], weight=fit["weight"], muscle=fit["muscle"])
    body = HumanService.create_human(macro_detail_dict=macro)
    body.name = "avatar_body"
    bake_shape(body)
    make_faceless(body)
    mannequin_material(body)
    data = LocationService.get_user_data()
    meas = garment_fit.measure_body(body)
    if spec.get("body_out"):  # first, so the viewer can show the bare avatar while the garments are built
        _export_one(body, spec["body_out"])
        print("BODY_DONE", flush=True)
    collider = make_collider(body)
    trunk = make_trunk(collider, meas)
    done = {}
    skip = set(spec.get("skip", []))  # debugging: steps to leave out (densify, settle, min_offset, crossings, drape)
    outfit = bool(spec.get("outfit"))  # worn together: inside -> out, each garment settles onto the previous ones
    pieces_in = list(spec.get("pieces", []))
    worn_objs = []  # (piece info, object) already on the avatar (outfit mode)
    if outfit:
        def _layer(pc):
            if pc.get("kind"):
                return cloth_sim.LAYER.get(pc["kind"], 3)
            if pc.get("type"):
                return cloth_sim.LAYER.get(templates.resolve(pc["type"], spec["sex"]).get("kind", "top"), 3)
            return 3
        pieces_in.sort(key=_layer)
    for piece in pieces_in:
        pid = piece.get("id", "?")
        try:
            if piece.get("type") and not piece.get("asset"):
                photo = json.load(open(piece["texture"])) if piece.get("texture") else None
                piece = {**templates.resolve(piece["type"], spec["sex"], photo, piece.get("length"),
                                             piece.get("sleeves")), **piece}
            kind = piece.get("kind", "top")
            if piece.get("pattern") and kind != "shoes" and os.path.exists(piece["pattern"]):
                # sewn from its 2D pattern around the body (cloth physics), like CLO3D / Marvelous Designer
                # garments under it (shoes excluded: trouser hems cover them, and pushing a hem out of a shoe
                # tears it in the solver)
                inner = [o for (pi_, o) in worn_objs if pi_.get("kind") != "shoes"]
                obj, pinfo = pattern_garment.build(piece["pattern"], piece, meas, body, collider, trunk, inner,
                                                   spec["sex"], f"garment_{pid}", frames=70)
                _export_one(obj, piece["out"])
                done[pid] = {"ok": True, "kind": kind, "method": "pattern", **{k: pinfo.get(k) for k in (
                    "length_m", "girth_cm", "sleeve_islands", "welded", "vertices")}}
                if outfit:
                    worn_objs.append(({"id": pid, "kind": kind, "gsm": piece.get("gsm")}, obj))
                else:
                    bpy.data.objects.remove(obj, do_unlink=True)
                for m in [m for m in body.modifiers if m.type == "MASK" or m.name.startswith("Delete.")]:
                    body.modifiers.remove(m)
                print("PART_DONE " + json.dumps({"id": pid, **done[pid]}), flush=True)
                continue
            folder = os.path.join(data, "clothes", piece["asset"])
            mhclo = next(os.path.join(folder, f) for f in os.listdir(folder) if f.endswith(".mhclo"))
            obj = HumanService.add_mhclo_asset(mhclo, body, asset_type="Clothes", subdiv_levels=0,
                                               set_up_rigging=False, interpolate_weights=False, import_subrig=False,
                                               import_weights=False)
            obj.name = f"garment_{pid}"
            if piece.get("part"):
                garment_fit.extract_part(obj, piece["part"], meas)
            push_off_skin(obj, LAYER_MM.get(kind, 8))
            if piece.get("color") and not piece.get("texture"):
                tint(obj, piece["color"])
            info = {}
            if piece.get("size") and kind != "shoes":
                info = garment_fit.resize(obj, collider, spec["sex"], piece["size"], piece.get("fit", "regular"),
                                          kind, meas, scale_length=piece.get("scale_length", True))
                # dresses: static fit (the cloth step below does the others)
                if kind == "dress" and (abs(info["scale_width"] - 1) > 0.06 or abs(info["scale_length"] - 1) > 0.06)                         and "drape" not in skip:
                    garment_fit.drape(obj, collider, piece.get("gsm", 180), kind=kind, trunk=trunk, under=[])
            # real cloth: the garment falls with its fabric onto the body (and, worn together, onto the garments
            # under it) from where it rests: collar / shoulders, waistband, straps. Natural folds, no crossing.
            inner = [o for (pi, o) in worn_objs if pi["kind"] != "shoes"]
            if kind not in ("shoes", "dress") and "settle" not in skip:
                # falls onto the BODY; the layers under it are handled geometrically afterwards (a cloth that
                # starts on another garment's thin open surface is unstable in the solver: tested)
                info["settle"] = cloth_sim.settle(obj, [collider], kind, piece.get("gsm"), frames=24)
            if kind != "shoes" and "densify" not in skip:  # small faces follow the body's curves (no face cutting through the hips)
                info["densified"] = garment_fit.densify(obj)
            if kind == "bottom":
                # a top must be able to cover the waist and seat: trousers stay within a graded distance of the
                # body there (4 mm at the waist -> 15 mm at the crotch -> free down the leg)
                info.update(garment_fit.max_offset(obj, collider, meas))
            if "min_offset" not in skip:
                info.update(garment_fit.min_offset(obj, collider, meas, kind))  # strict layer order
            if "crossings" not in skip:
                info.update(garment_fit.resolve_crossings(obj, collider, kind))  # no face under the skin
            base_co = [v.co.copy() for v in obj.data.vertices]  # its own shape, worn alone (animation start)
            if inner:  # worn over other garments: just outside them
                info["lifted_after"] = cloth_sim.push_outside(obj, inner, gap=0.006)
            info["flipped"] = garment_fit.orient_outward(obj, collider)  # no dark inside-out faces
            if piece.get("texture"):
                garment_texture.apply(obj, meas, piece["texture"], kind)
            make_opaque(obj)
            _export_one(obj, piece["out"])
            done[pid] = {"ok": True, "kind": kind, "template": piece["asset"],
                         "scale_width": info.get("scale_width"), "scale_length": info.get("scale_length"),
                         "hang": info.get("hang"), "hang_vertices": info.get("hang_vertices"),
                         "min_offset_moved": info.get("min_offset_moved"), "densified": info.get("densified"),
                         "crossings": info.get("crossings"), "settle": info.get("settle"),
                         "lifted": info.get("lifted"), "lifted_after": info.get("lifted_after")}
            if outfit:
                worn_objs.append(({"id": pid, "kind": kind, "gsm": piece.get("gsm"), "base_co": base_co}, obj))
            else:
                bpy.data.objects.remove(obj, do_unlink=True)
        except Exception as e:  # noqa: BLE001
            done[pid] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        for m in [m for m in body.modifiers if m.type == "MASK" or m.name.startswith("Delete.")]:
            body.modifiers.remove(m)  # MPFB hides the body under each garment: the body is exported whole
        print("PART_DONE " + json.dumps({"id": pid, **done[pid]}), flush=True)
    result = {"fit": fit, "body": {k: v for k, v in meas.items() if k.endswith("_cm")}, "pieces": done}
    if outfit and spec.get("animate") and worn_objs:
        try:  # the avatar turns on the spot, every garment is cloth: motion baked into morph targets
            result["animation"] = cloth_sim.animate(collider, worn_objs, spec["anim_dir"])
        except Exception as e:  # noqa: BLE001
            result["animation"] = {"error": f"{type(e).__name__}: {e}"}
    bpy.data.objects.remove(collider, do_unlink=True)
    bpy.data.objects.remove(trunk, do_unlink=True)
    return result


def render_preview(path: str) -> None:
    sc = bpy.context.scene
    bpy.ops.object.camera_add(location=(0, -3.6, 0.95), rotation=(math.radians(90), 0, 0))
    sc.camera = bpy.context.object
    sc.camera.data.lens = 45
    bpy.ops.object.light_add(type="AREA", location=(1.5, -3, 3))
    bpy.context.object.data.energy, bpy.context.object.data.size = 700, 4
    bpy.ops.object.light_add(type="AREA", location=(-2, -2, 1.5))
    bpy.context.object.data.energy, bpy.context.object.data.size = 250, 3
    for x in (1.8, -1.8):  # back lights, so a back view is readable too
        bpy.ops.object.light_add(type="AREA", location=(x, 3, 2.5))
        bpy.context.object.data.energy, bpy.context.object.data.size = 450, 4
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x, sc.render.resolution_y = 700, 1000
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)


def ensure_mpfb() -> None:
    """Headless Blender runs the script before user extensions are registered: enable MPFB explicitly."""
    import addon_utils

    mod = "bl_ext.user_default.mpfb"
    if not addon_utils.check(mod)[1]:
        addon_utils.enable(mod, default_set=True, persistent=True)


if __name__ == "__main__" and "--" in sys.argv:  # headless: blender -b --python build_avatar.py -- spec.json
    ensure_mpfb()
    spec = json.load(open(sys.argv[sys.argv.index("--") + 1]))
    result = build_parts(spec) if spec.get("mode") == "parts" else build(spec)
    print("BUILD_RESULT " + json.dumps(result, default=str))
