"""Bake day/night prelight into the SA-MP house interiors (Blender + DragonFF, run headless).

usage: blender --background --factory-startup --python tools/bake_interiors.py -- <original dir> <out dir> [house ...]

Each interior is baked with its exterior loaded as an occluder, so the roof and outer walls shade it. Cycles ambient
occlusion becomes the light level, mapped onto day/night ranges (SA doubles prelight, so 0.48 is ~95% of the texture in
open floor by day; corners fall to about half; night is a warm, dim lamp level).
"""

import sys
from pathlib import Path

import addon_utils
import bpy

AO_DISTANCE = 2.5  # metres; a room-sized falloff, so corners and the space under the roof darken
SAMPLES = 128
# sRGB 0..1 prelight at full occlusion (ao = 0) and fully open (ao = 1)
DAY = ((0.24, 0.23, 0.22), (0.48, 0.47, 0.45))
NIGHT = ((0.06, 0.05, 0.04), (0.17, 0.145, 0.11))
HOUSES = [f"{zone}house{i}" for zone in ("sf", "lv", "ls") for i in range(1, 5)]


def reset() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("DragonFF", default_set=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = SAMPLES
    scene.render.bake.target = "VERTEX_COLORS"
    scene.world = bpy.data.worlds.new("bake")
    scene.world.light_settings.distance = AO_DISTANCE


def import_dff(path: Path) -> list:
    before = set(bpy.data.objects)
    bpy.ops.import_scene.dff(filepath=str(path), read_mat_split=True, remove_doubles=False)  # SA-MP keeps material ids only in the BinMesh; keep every face
    return [o for o in bpy.data.objects if o not in before and o.type == "MESH"]


def lerp(lo, hi, t):
    return [a + (b - a) * t for a, b in zip(lo, hi)]


def bake(obj) -> None:
    mesh = obj.data
    while mesh.color_attributes:
        mesh.color_attributes.remove(mesh.color_attributes[0])
    ao = mesh.color_attributes.new("ao", "FLOAT_COLOR", "CORNER")
    mesh.color_attributes.active_color = ao
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.bake(type="AO")
    levels = [sum(c.color[:3]) / 3 for c in ao.data]
    day = mesh.color_attributes.new("day", "BYTE_COLOR", "CORNER")
    night = mesh.color_attributes.new("night", "BYTE_COLOR", "CORNER")
    for i, t in enumerate(levels):
        day.data[i].color_srgb = (*lerp(*DAY, t), 1.0)
        night.data[i].color_srgb = (*lerp(*NIGHT, t), 1.0)
    mesh.color_attributes.remove(mesh.color_attributes["ao"])
    obj.dff.day_cols = True
    obj.dff.night_cols = True


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1 :]
    src, out, houses = Path(args[0]), Path(args[1]), args[2:] or HOUSES
    out.mkdir(parents=True, exist_ok=True)
    for house in houses:
        reset()
        import_dff(src / f"{house}.dff")
        interior = import_dff(src / f"{house}int.dff")
        for obj in interior:
            bake(obj)
            whiten_materials(obj)
        bpy.ops.object.select_all(action="DESELECT")
        for obj in interior:
            obj.select_set(True)
        target = out / f"{house}int.dff"
        bpy.ops.export_dff.scene(filepath=str(target), only_selected=True, export_version="0x36003")
        print(f"baked {house}int -> {target}")


def whiten_materials(obj) -> None:
    """SA multiplies texture x prelight x material colour; the originals' 127 grey would halve the baked light.

    DragonFF exports the Principled BSDF base colour as the material colour.
    """
    for slot in obj.material_slots:
        for node in slot.material.node_tree.nodes if slot.material and slot.material.node_tree else []:
            if node.type == "BSDF_PRINCIPLED":
                alpha = node.inputs["Base Color"].default_value[3]
                node.inputs["Base Color"].default_value = (1.0, 1.0, 1.0, alpha)


main()
