"""Open a house in the Blender GUI: original interior (left) next to the baked one (right), lit the way the game does.

usage: blender --python tools/view_house.py -- [house]   (default lshouse1; run from the repo root)

Materials are flat emission: texture x prelight x 2, blended day->night by the scene's "night" property (Scene
properties > Custom Properties, 0..1). The original interior has no prelight, so it is shown with the texture alone.
The exterior is in the "exterior" collection, hidden so the roofless rooms can be seen from above; tick it to show it.
"""

import sys
from pathlib import Path

import addon_utils
import bpy

TXD = {
    **{f"sfhouse{i}": "boxhses_sfsx" for i in range(1, 5)},
    "lvhouse1": "vegashse2",
    "lvhouse2": "vegashse3",
    "lvhouse3": "vegashse6",
    "lvhouse4": "vegashse4",
    "lshouse1": "ganghouse1_lax",
    "lshouse2": "ganghouse1_lax",
    "lshouse3": "comedhos1_la",
    "lshouse4": "glenphouse_lax",
}
GAP = 16.0  # metres between the before and after interiors


def import_into(collection_name: str, dff: Path, txds: list[Path]) -> list:
    """DragonFF makes its own collection per file; rename it so the outliner reads before/after/exterior."""
    before_objects, before_collections = set(bpy.data.objects), set(bpy.data.collections)
    bpy.ops.import_scene.dff(filepath=str(dff), read_mat_split=True, remove_doubles=False)  # SA-MP keeps material ids only in the BinMesh; keep every face
    for txd in txds:
        bpy.ops.import_scene.dff(filepath=str(txd), txd_apply_to_objects=True)
    for collection in set(bpy.data.collections) - before_collections:
        collection.name = collection_name
    return [o for o in bpy.data.objects if o not in before_objects]


def texture(name: str):
    """TXD images are named '<txd>/<texture>/<mip>'; DFF texture names do not always match their case."""
    wanted = name.rsplit(".", 1)[0].lower()
    return next((i for i in bpy.data.images if i.name.count("/") == 2 and i.name.split("/")[1].lower() == wanted), None)


def flat_material(source, obj, prelit: bool):
    """Emission copy of an imported material: texture (x prelight day/night mix x 2)."""
    image = next((n.image for n in source.node_tree.nodes if n.type == "TEX_IMAGE" and n.image), None) if source and source.node_tree else None
    if image and image.name.count("/") != 2:
        image = texture(image.name) or image
    mat = bpy.data.materials.new(f"{obj.name}:{source.name if source else 'none'}")
    mat.use_nodes = True
    mat.use_backface_culling = True  # the game culls back faces; this also lets you look into the roofless rooms
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    emit = nodes.new("ShaderNodeEmission")
    links.new(emit.outputs[0], out.inputs[0])
    colour = emit.inputs["Color"]
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = image
    if not prelit:
        links.new(tex.outputs[0], colour)
        return mat
    names = [a.name for a in obj.data.color_attributes]
    day, night = nodes.new("ShaderNodeVertexColor"), nodes.new("ShaderNodeVertexColor")
    day.layer_name, night.layer_name = names[0], names[1] if len(names) > 1 else names[0]
    blend = nodes.new("ShaderNodeMix")
    blend.data_type = "RGBA"
    driver = blend.inputs["Factor"].driver_add("default_value").driver
    var = driver.variables.new()
    var.targets[0].id_type = "SCENE"
    var.targets[0].id = bpy.context.scene
    var.targets[0].data_path = '["night"]'
    driver.expression = var.name
    links.new(day.outputs[0], blend.inputs[6])
    links.new(night.outputs[0], blend.inputs[7])
    lit = nodes.new("ShaderNodeMix")
    lit.data_type, lit.blend_type = "RGBA", "MULTIPLY"
    lit.inputs["Factor"].default_value = 1.0
    links.new(tex.outputs[0], lit.inputs[6])
    links.new(blend.outputs[2], lit.inputs[7])
    emit.inputs["Strength"].default_value = 2.0
    links.new(lit.outputs[2], colour)
    return mat


def restyle(objects: list, prelit: bool) -> None:
    for obj in objects:
        if obj.type != "MESH":
            continue
        for slot in obj.material_slots:
            slot.material = flat_material(slot.material, obj, prelit and len(obj.data.color_attributes) > 0)


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    house = args[0] if args else "lshouse1"
    root = Path.cwd()
    addon_utils.enable("DragonFF", default_set=True)
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    for collection in list(bpy.data.collections):
        bpy.data.collections.remove(collection)
    scene = bpy.context.scene
    scene.view_settings.view_transform = "Standard"  # AgX would desaturate the textures
    scene.view_settings.look = "None"
    scene["night"] = 0.0
    scene.id_properties_ui("night").update(min=0.0, max=1.0, soft_min=0.0, soft_max=1.0, description="0 = noon prelight, 1 = midnight")
    scene.world = bpy.data.worlds.new("sky")
    scene.world.color = (0.02, 0.02, 0.025)
    walls = [root / "work" / "txd" / "all_walls.txd"]
    exterior = import_into("exterior", root / "models" / "original" / f"{house}.dff", [root / "work" / "txd" / f"{TXD[house]}.txd"])
    before = import_into("before", root / "models" / "original" / f"{house}int.dff", walls)
    after = import_into("after", root / "models" / "baked" / f"{house}int.dff", walls)
    restyle(exterior, prelit=True)
    restyle(before, prelit=False)
    restyle(after, prelit=True)
    for obj in before:
        if obj.parent is None:
            obj.location.x -= GAP
    bpy.context.view_layer.layer_collection.children["exterior"].hide_viewport = True
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type == "VIEW_3D":
            space = area.spaces[0]
            space.shading.type = "MATERIAL"
            space.overlay.show_floor = False
            r3d = space.region_3d
            r3d.view_location = (-GAP / 2, 0, 0)
            r3d.view_distance = 34
            r3d.view_rotation = (0.82, 0.42, 0.18, 0.35)
    if not bpy.app.background:
        bpy.ops.wm.save_as_mainfile(filepath=str(root / "work" / f"{house}.blend"))


main()
