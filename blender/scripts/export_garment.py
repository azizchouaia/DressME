"""Export a garment authored in Blender to a web-ready GLB.

Run inside Blender (offline / server-side, never in the frontend):

    blender garment.blend --background --python blender/scripts/export_garment.py -- \
        --output frontend/public/models/garments/my_shirt.glb --max-faces 12000

Conventions every garment must follow so it lines up with base_avatar.glb:
  * Y up (Blender Z up is converted by the exporter), meters, feet at origin.
  * Modelled directly over the base avatar in its rest pose; no rig, no animation.
  * One object per material where possible; textures at most 1024px.
"""

import argparse
import sys

import bpy  # type: ignore[import-not-found]


def parse_args() -> argparse.Namespace:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-faces", type=int, default=12000)
    parser.add_argument("--hide", nargs="*", default=["BaseAvatar"],
                        help="Objects to exclude, e.g. the reference avatar.")
    return parser.parse_args(argv)


def decimate_to_budget(max_faces: int) -> None:
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.visible_get()]
    total = sum(len(o.data.polygons) for o in meshes)
    if total <= max_faces:
        return
    ratio = max_faces / total
    for obj in meshes:
        modifier = obj.modifiers.new(name="WebDecimate", type="DECIMATE")
        modifier.ratio = ratio


def main() -> None:
    args = parse_args()
    for name in args.hide:
        obj = bpy.data.objects.get(name)
        if obj:
            obj.hide_set(True)
            obj.hide_render = True

    decimate_to_budget(args.max_faces)
    bpy.ops.export_scene.gltf(
        filepath=args.output,
        export_format="GLB",
        use_visible=True,
        export_apply=True,
        export_yup=True,
        export_animations=False,
        export_skins=False,
        export_draco_mesh_compression_enable=False,
        export_image_format="AUTO",
    )
    print(f"Exported {args.output}")


if __name__ == "__main__":
    main()
