"""Render every house in Blender, SA-MP's original next to this repo's, at noon and at midnight, for docs/houses.md.

usage: blender --python tools/render_houses.py -- [house ...]   (run from the repo root; works headless too)

Each state (original: models/original, reworked: models/baked) loads the exterior with its interior, so the glass has
a room behind it. Materials are flat emission the way the game lights buildings: texture x material colour x 2 x
prelight, the prelight blended from the day to the night colours; a model without prelight (the original interiors)
gets the texture as is, day or night. Midnight renders are exposed 1.3 stops up so they stay readable. Alpha comes from the texture and the material colour. The camera looks from the
corner between the two walls with the most window area (data/windows.json). Raw renders go to work/renders/, and
tools/gallery.py turns them into screenshots/houses/<house>.png.
"""

import json
import math
import sys
from pathlib import Path

import addon_utils
import bpy
from mathutils import Vector

ROOT = Path.cwd()
HOUSES = [f"{zone}house{i}" for zone in ("ls", "sf", "lv") for i in range(1, 5)]
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
SKY = {"noon": (0.45, 0.62, 0.82), "midnight": (0.012, 0.016, 0.03)}
GROUND = {"noon": (0.22, 0.24, 0.18), "midnight": (0.02, 0.022, 0.025)}
SIZE = (1200, 760)
LENS = 40  # mm
ELEVATION = math.radians(14)
NIGHT_EXPOSURE = 1.3  # stops; the game adds ambient light to buildings at night, a flat render would be near black


def reset() -> None:
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.collections, bpy.data.cameras):
        for item in list(block):
            block.remove(item)
    for image in list(bpy.data.images):  # keep decoded TXD textures ('<txd>/<texture>/<mip>'): decoding is the slow part
        if image.name.count("/") != 2:
            bpy.data.images.remove(image)


def load(dff: Path, txds: list[Path]) -> list:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.dff(filepath=str(dff), read_mat_split=True, remove_doubles=False)  # SA-MP keeps material ids only in the BinMesh
    for txd in txds:
        # DragonFF decodes TXDs in pure Python; decode each once per session, texture() then finds the images by name
        if not any(i.name.lower().startswith(txd.name.lower() + "/") for i in bpy.data.images):
            bpy.ops.import_scene.dff(filepath=str(txd), txd_apply_to_objects=False)
    return [o for o in bpy.data.objects if o not in before and o.type == "MESH"]


def texture(source):
    """The material's image, matched to the TXD import by name ('<txd>/<texture>/<mip>', case varies)."""
    image = next((n.image for n in source.node_tree.nodes if n.type == "TEX_IMAGE" and n.image), None) if source.node_tree else None
    if image is None or image.name.count("/") == 2:
        return image
    wanted = image.name.rsplit(".", 1)[0].lower()
    return next((i for i in bpy.data.images if i.name.count("/") == 2 and i.name.split("/")[1].lower() == wanted), image)


def game_material(source, obj):
    nodes_mat = bpy.data.materials.new(f"{obj.name}:{source.name}")
    nodes_mat.use_nodes = True
    nodes_mat.use_backface_culling = True
    colour = list(source.diffuse_color)  # DragonFF keeps the RW material colour (0..1) and alpha here
    nt = nodes_mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    emit = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(clear.outputs[0], mix.inputs[1])
    nt.links.new(emit.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs[0])
    # SA multiplies raw 0..255 values, so the products are taken in gamma space and converted back at the end
    def gamma(socket, power):
        node = nt.nodes.new("ShaderNodeGamma")
        node.inputs["Gamma"].default_value = power
        nt.links.new(socket, node.inputs["Color"])
        return node.outputs[0]

    def multiply(a, b):
        node = nt.nodes.new("ShaderNodeMix")
        node.data_type, node.blend_type = "RGBA", "MULTIPLY"
        node.inputs["Factor"].default_value = 1.0
        nt.links.new(a, node.inputs[6])
        if isinstance(b, tuple):
            node.inputs[7].default_value = b
        else:
            nt.links.new(b, node.inputs[7])
        return node.outputs[2]

    tint = nt.nodes.new("ShaderNodeRGB")
    tint.outputs[0].default_value = (*colour[:3], 1)  # raw material colour, already a gamma-space value
    rgb, alpha = tint.outputs[0], None
    image = texture(source)
    if image is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        rgb, alpha = multiply(gamma(tex.outputs["Color"], 1 / 2.2), tint.outputs[0]), tex.outputs["Alpha"]
    layers = [a.name for a in obj.data.color_attributes]
    if layers:
        day, night = nt.nodes.new("ShaderNodeVertexColor"), nt.nodes.new("ShaderNodeVertexColor")
        day.layer_name, night.layer_name = layers[0], layers[1] if len(layers) > 1 else layers[0]
        blend = nt.nodes.new("ShaderNodeMix")
        blend.data_type = "RGBA"
        driver = blend.inputs["Factor"].driver_add("default_value").driver
        var = driver.variables.new()
        var.targets[0].id_type, var.targets[0].id, var.targets[0].data_path = "SCENE", bpy.context.scene, '["night"]'
        driver.expression = var.name
        nt.links.new(day.outputs[0], blend.inputs[6])
        nt.links.new(night.outputs[0], blend.inputs[7])
        rgb = multiply(multiply(rgb, gamma(blend.outputs[2], 1 / 2.2)), (2.0, 2.0, 2.0, 1.0))  # SA doubles prelight
    nt.links.new(gamma(rgb, 2.2), emit.inputs["Color"])
    if alpha is not None or colour[3] < 1:
        times = nt.nodes.new("ShaderNodeMath")
        times.operation = "MULTIPLY"
        times.inputs[1].default_value = colour[3]
        if alpha is not None:
            nt.links.new(alpha, times.inputs[0])
        else:
            times.inputs[0].default_value = 1.0
        nt.links.new(times.outputs[0], mix.inputs[0])
        nodes_mat.surface_render_method = "BLENDED" if colour[3] < 1 else "DITHERED"
        nodes_mat.use_backface_culling = colour[3] >= 1
    else:
        mix.inputs[0].default_value = 1.0
    return nodes_mat


def restyle(objects: list) -> None:
    for obj in objects:
        for slot in obj.material_slots:
            if slot.material:
                slot.material = game_material(slot.material, obj)


def view_direction(house: str) -> Vector:
    """Diagonal between the two outward wall directions with the most glass, so the shot shows the windows."""
    windows = json.loads((ROOT / "data" / "windows.json").read_text()).get(house, [])
    area = {}
    for w in windows:
        n = Vector(w["normal"]).normalized()
        key = (round(n.x), round(n.y))
        area[key] = area.get(key, 0) + w["width"] * w["height"]
    best = sorted(area, key=area.get, reverse=True)[:2] or [(1, 0)]
    if len(best) == 2 and best[0] == tuple(-c for c in best[1]):  # opposite walls: show the busiest one, turned 35 degrees
        a = math.atan2(best[0][1], best[0][0]) + math.radians(35)
        return Vector((math.cos(a), math.sin(a), 0))
    return sum((Vector((x, y, 0)) for x, y in best), Vector()).normalized()


def stage(house: str, objects: list, body: list) -> None:
    """Ground, sky and camera. The camera frames the body (the interior's bounds), not yards and walls around it."""
    scene = bpy.context.scene
    points = [o.matrix_world @ Vector(c) for o in body for c in o.bound_box]
    lo = Vector([min(p[i] for p in points) for i in range(3)])
    hi = Vector([max(p[i] for p in points) for i in range(3)])
    centre, radius = (lo + hi) / 2, (hi - lo).length / 2
    ground = bpy.data.meshes.new("ground")
    s = radius * 6
    ground.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    plane = bpy.data.objects.new("ground", ground)
    plane.location = (centre.x, centre.y, min(p.z for o in objects for p in (o.matrix_world @ Vector(c) for c in o.bound_box)) + 0.02)
    scene.collection.objects.link(plane)
    mat = bpy.data.materials.new("ground")
    mat.use_nodes = True
    emit = mat.node_tree.nodes.new("ShaderNodeEmission")
    mat.node_tree.links.new(emit.outputs[0], mat.node_tree.nodes["Material Output"].inputs[0])
    plane.data.materials.append(mat)
    plane["emission"] = emit.name
    direction = view_direction(house)
    eye_dir = Vector((direction.x * math.cos(ELEVATION), direction.y * math.cos(ELEVATION), math.sin(ELEVATION)))
    fov = 2 * math.atan(36 / 2 / LENS)
    cam_data = bpy.data.cameras.new("cam")
    cam_data.lens = LENS
    cam = bpy.data.objects.new("cam", cam_data)
    cam.location = centre + eye_dir * (radius / math.sin(fov / 2) * 1.25)
    cam.rotation_euler = (-eye_dir).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(cam)
    scene.camera = cam


def render(house: str, state: str, out: Path) -> None:
    scene = bpy.context.scene
    ground = bpy.data.objects["ground"]
    emit = ground.data.materials[0].node_tree.nodes[ground["emission"]]
    for time, night in (("noon", 0.0), ("midnight", 1.0)):
        scene["night"] = night
        next(n for n in scene.world.node_tree.nodes if n.type == "BACKGROUND").inputs["Color"].default_value = (*SKY[time], 1)
        emit.inputs["Color"].default_value = (*GROUND[time], 1)
        scene.view_settings.exposure = NIGHT_EXPOSURE if night else 0.0
        scene.render.filepath = str(out / f"{house}-{state}-{time}.png")
        bpy.ops.render.render(write_still=True)
        print(f"rendered {scene.render.filepath}")


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    addon_utils.enable("DragonFF", default_set=True)
    scene = bpy.context.scene
    for engine in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = engine
            break
        except TypeError:
            continue
    scene.render.resolution_x, scene.render.resolution_y = SIZE
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.render.film_transparent = False
    out = ROOT / "work" / "renders"
    out.mkdir(parents=True, exist_ok=True)
    for house in args or HOUSES:
        for state, folder in (("original", "original"), ("reworked", "baked")):
            reset()
            scene.world = bpy.data.worlds.get("sky") or bpy.data.worlds.new("sky")
            scene.world.use_nodes = True  # a world without nodes renders grey whatever its colour
            scene["night"] = 0.0
            txd = ROOT / "work" / "txd"
            objects = load(ROOT / "models" / folder / f"{house}.dff", [txd / f"{TXD[house]}.txd"])
            interior = load(ROOT / "models" / folder / f"{house}int.dff", [txd / "all_walls.txd"])
            restyle(objects + interior)
            stage(house, objects + interior, interior)
            render(house, state, out)


main()
