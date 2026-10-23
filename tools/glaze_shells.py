"""Fit a pane into every window hole of the shell exteriors (Blender + DragonFF, run headless).

usage: blender --background --factory-startup --python tools/glaze_shells.py -- <original dir> <seeds.json> <out.json> [house ...]

For each seed from tools/window_seeds.py, rays are cast straight through the wall on a 4 cm grid around it. The open
cells connected to the seed are the hole; their bounds are the opening, and the wall faces hit just outside it give
the depth. Openings that run off the search area (doorways, open sides) are dropped, duplicates merged. The result is
data/windows.json: per house, a list of openings in the model's own frame.
"""

import json
import sys
from collections import deque
from pathlib import Path

import addon_utils
import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

STEP = 0.04
REACH_T, REACH_Z = 3.0, 2.0  # metres searched either side of the seed, along the wall and vertically
PROBE = 0.8  # rays start this far in front of the seed and run twice as far


def load_bvh(path: Path) -> BVHTree:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    addon_utils.enable("DragonFF", default_set=True)
    bpy.ops.import_scene.dff(filepath=str(path), read_mat_split=True, remove_doubles=False)
    bm = bmesh.new()
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            part = bmesh.new()
            part.from_mesh(obj.data)
            part.transform(obj.matrix_world)
            mesh = bpy.data.meshes.new("tmp")
            part.to_mesh(mesh)
            bm.from_mesh(mesh)
    return BVHTree.FromBMesh(bm)


def fit(bvh: BVHTree, centre: Vector, normal: Vector) -> dict | None:
    up = Vector((0, 0, 1))
    tangent = up.cross(normal)
    nt, nz = round(REACH_T / STEP), round(REACH_Z / STEP)

    def point(i: int, j: int) -> Vector:
        return centre + tangent * (i * STEP) + up * (j * STEP)

    def is_open(i: int, j: int) -> bool:
        return bvh.ray_cast(point(i, j) - normal * PROBE, normal, 2 * PROBE)[0] is None

    start = min(((i, j) for i in range(-12, 13) for j in range(-12, 13) if is_open(i, j)), key=lambda c: c[0] ** 2 + c[1] ** 2, default=None)
    if start is None:
        return None
    seen, queue = {start}, deque([start])
    while queue:
        i, j = queue.popleft()
        if abs(i) >= nt or abs(j) >= nz:
            return None  # leaks out of the search area: not a window
        for c in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if c not in seen and is_open(*c):
                seen.add(c)
                queue.append(c)
    i0, i1 = min(c[0] for c in seen), max(c[0] for c in seen)
    j0, j1 = min(c[1] for c in seen), max(c[1] for c in seen)
    depths = []
    for i, j in [(i, j0 - 1) for i in range(i0, i1 + 1)] + [(i, j1 + 1) for i in range(i0, i1 + 1)] + [(i0 - 1, j) for j in range(j0, j1 + 1)] + [(i1 + 1, j) for j in range(j0, j1 + 1)]:
        front = bvh.ray_cast(point(i, j) - normal * PROBE, normal, 2 * PROBE)[0]
        back = bvh.ray_cast(point(i, j) + normal * PROBE, -normal, 2 * PROBE)[0]
        if front and back:
            depths.append(((front + back) / 2 - centre).dot(normal))
    depth = sorted(depths)[len(depths) // 2] if depths else 0.0
    mid = centre + normal * depth + tangent * ((i0 + i1) / 2 * STEP) + up * ((j0 + j1) / 2 * STEP)
    return {
        "centre": [round(v, 3) for v in mid],
        "normal": [round(v, 3) for v in normal],
        "width": round((i1 - i0 + 1) * STEP, 3),
        "height": round((j1 - j0 + 1) * STEP, 3),
        "open_cells": len(seen),
        "cells": (i1 - i0 + 1) * (j1 - j0 + 1),
    }


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1 :]
    src, seeds_path, out = Path(args[0]), Path(args[1]), Path(args[2])
    seeds = json.loads(seeds_path.read_text())
    houses = args[3:] or list(seeds)
    result = json.loads(out.read_text()) if out.exists() else {}
    for house in houses:
        bvh = load_bvh(src / f"{house}.dff")
        openings = []
        for seed in seeds[house]:
            normal = Vector((1, 0, 0)) if seed["normal"] == "x" else Vector((0, 1, 0))
            hole = fit(bvh, Vector(seed["centre"]), normal)
            if hole and not any((Vector(hole["centre"]) - Vector(o["centre"])).length < 0.3 for o in openings):
                openings.append(hole)
        result[house] = openings
        print(f"{house}: {len(seeds[house])} seeds -> {len(openings)} openings")
        for o in openings:
            print(f"   {o}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1) + "\n")


main()
