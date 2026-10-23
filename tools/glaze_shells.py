"""Fit a pane into every window hole of the shell exteriors (Blender + DragonFF, run headless).

usage: blender --background --factory-startup --python tools/glaze_shells.py -- <original dir> <seeds.json> <out.json> [house ...]

Seeds come from two places: tools/window_seeds.py (where maps put window001) and a scan of the model itself. The scan
sweeps the exterior with horizontal rays from 8 directions, groups the hits into wall planes, and takes every enclosed,
roughly rectangular gap in a plane as a seed; maps only glaze some holes (lshouse3 has 1 seed, lvhouse4's never fit).
Each seed is then fitted: rays are cast straight through the wall on a 4 cm grid around it, the open cells connected to
the seed are the hole, their bounds are the opening, and the wall faces hit just outside it give the depth. Openings
that run off the search area (open sides) are dropped, and scanned ones that hold a map door object (entrances), are
not fully rectangular (arched doorways) or are over 2.4 m tall (garages), duplicates merged. Each opening's normal is turned to face out of the house (the interior model is near on the inside), and the
wall thickness around it is kept. The result is data/windows.json: per house, a list of openings in the model's own
frame.
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
SCAN = 0.1  # grid of the whole-model scan
MIN_WALL_CELLS = 40  # a plane needs this many hits to count as a wall
MAX_WINDOW = (5.0, 2.4)  # widest and tallest scanned opening; taller is a garage


def load_bvh(path: Path) -> tuple[BVHTree, Vector, Vector]:
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
    lo = Vector([min(v.co[i] for v in bm.verts) for i in range(3)])
    hi = Vector([max(v.co[i] for v in bm.verts) for i in range(3)])
    return BVHTree.FromBMesh(bm), lo, hi


def scan(bvh: BVHTree, lo: Vector, hi: Vector) -> list[tuple[Vector, Vector]]:
    """(centre, outward normal) of every enclosed gap in a wall plane, seen from 8 horizontal directions."""
    import math

    up, middle = Vector((0, 0, 1)), (lo + hi) / 2
    reach = (hi - lo).length / 2 + 1
    seeds = []
    for k in range(8):
        normal = Vector((math.cos(k * math.pi / 4), math.sin(k * math.pi / 4), 0))
        tangent = up.cross(normal)
        nu, nz = int(reach / SCAN), int((hi.z - lo.z) / 2 / SCAN) + 1
        planes = {}  # plane offset along the normal -> {(i, j)}
        for i in range(-nu, nu + 1):
            for j in range(-nz, nz + 1):
                origin = middle + tangent * (i * SCAN) + up * (j * SCAN) + normal * reach
                hit, hit_normal, _, distance = bvh.ray_cast(origin, -normal, 2 * reach)
                if hit is not None and abs(hit_normal.dot(normal)) > 0.95:
                    planes.setdefault(round((reach - distance) / 0.05), set()).add((i, j))
        for offset, wall in planes.items():
            if len(wall) < MIN_WALL_CELLS:
                continue
            depth = offset * 0.05

            def point(i: int, j: int) -> Vector:
                return middle + tangent * (i * SCAN) + up * (j * SCAN) + normal * depth

            def is_open(i: int, j: int) -> bool:
                return bvh.ray_cast(point(i, j) + normal * 0.4, -normal, 0.8)[0] is None

            i0, i1 = min(c[0] for c in wall), max(c[0] for c in wall)
            j0, j1 = min(c[1] for c in wall), max(c[1] for c in wall)
            seen = set(wall)
            for i in range(i0 + 1, i1):
                for j in range(j0 + 1, j1):
                    if (i, j) in seen or not is_open(i, j):
                        continue
                    region, queue, enclosed = {(i, j)}, deque([(i, j)]), True
                    seen.add((i, j))
                    while queue and enclosed:
                        a, b = queue.popleft()
                        for c in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                            if c in wall or c in region:
                                continue
                            if not (i0 <= c[0] <= i1 and j0 <= c[1] <= j1) or len(region) > 4000:
                                enclosed = False
                                break
                            if is_open(*c):  # anything solid (the wall, a reveal, a sill) bounds the hole
                                region.add(c)
                                seen.add(c)
                                queue.append(c)
                    if not enclosed:
                        continue
                    a0, a1 = min(c[0] for c in region), max(c[0] for c in region)
                    b0, b1 = min(c[1] for c in region), max(c[1] for c in region)
                    w, h = (a1 - a0 + 1) * SCAN, (b1 - b0 + 1) * SCAN
                    if 0.3 <= w <= MAX_WINDOW[0] and 0.3 <= h <= MAX_WINDOW[1] and len(region) >= 0.7 * (a1 - a0 + 1) * (b1 - b0 + 1):
                        seeds.append((point((a0 + a1) / 2, (b0 + b1) / 2), normal.copy()))
    return seeds


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
    depths, thicknesses = [], []
    for i, j in [(i, j0 - 1) for i in range(i0, i1 + 1)] + [(i, j1 + 1) for i in range(i0, i1 + 1)] + [(i0 - 1, j) for j in range(j0, j1 + 1)] + [(i1 + 1, j) for j in range(j0, j1 + 1)]:
        front = bvh.ray_cast(point(i, j) - normal * PROBE, normal, 2 * PROBE)[0]
        back = bvh.ray_cast(point(i, j) + normal * PROBE, -normal, 2 * PROBE)[0]
        if front and back:
            depths.append(((front + back) / 2 - centre).dot(normal))
            thicknesses.append((back - front).dot(normal))
    depth = sorted(depths)[len(depths) // 2] if depths else 0.0
    thickness = sorted(thicknesses)[len(thicknesses) // 2] if thicknesses else 0.0
    mid = centre + normal * depth + tangent * ((i0 + i1) / 2 * STEP) + up * ((j0 + j1) / 2 * STEP)
    return {
        "centre": [round(v, 3) for v in mid],
        "normal": [round(v, 3) for v in normal],
        "width": round((i1 - i0 + 1) * STEP, 3),
        "height": round((j1 - j0 + 1) * STEP, 3),
        "thickness": round(max(thickness, 0.0), 3),  # wall faces either side of the opening; 0 for a single-sided wall
        "open_cells": len(seen),
        "cells": (i1 - i0 + 1) * (j1 - j0 + 1),
    }


def holds_door(hole: dict, doors: list[dict]) -> bool:
    """True when a map door object sits inside the opening (within half a metre of its rectangle)."""
    centre, normal = Vector(hole["centre"]), Vector(hole["normal"])
    tangent = Vector((0, 0, 1)).cross(normal)
    for door in doors:
        d = Vector(door["centre"]) - centre
        if abs(d.dot(normal)) < 1.0 and abs(d.dot(tangent)) < hole["width"] / 2 + 0.5 and abs(d.z) < hole["height"] / 2 + 0.5:
            return True
    return False


def outward(rooms: BVHTree, hole: dict) -> dict:
    """Point the opening's normal out of the house and measure the reveal.

    The exterior walls are single planes; the inside face of the wall belongs to the interior model. Just above and
    beside the opening, a ray into the room meets that face within centimetres, while a ray outwards meets nothing.
    The median distance on the inside is the reveal depth (the wall thickness the window sits in).
    """
    centre, normal = Vector(hole["centre"]), Vector(hole["normal"])
    tangent = Vector((0, 0, 1)).cross(normal)
    probes = [centre + Vector((0, 0, hole["height"] / 2 + 0.15)) + tangent * u for u in (-hole["width"] / 3, 0, hole["width"] / 3)]
    probes += [centre + tangent * (side * (hole["width"] / 2 + 0.15)) for side in (-1, 1)]
    votes, reveals = 0, []
    for p in probes:
        ahead = rooms.ray_cast(p - normal * 0.01, normal, 1.5)
        behind = rooms.ray_cast(p + normal * 0.01, -normal, 1.5)
        da = ahead[3] if ahead[0] is not None else None
        db = behind[3] if behind[0] is not None else None
        if da is not None and (db is None or da < db):
            votes += 1  # the room is ahead: the normal points in
            reveals.append(da)
        elif db is not None:
            votes -= 1
            reveals.append(db)
    reveal = round(sorted(reveals)[len(reveals) // 2], 3) if reveals else 0.0
    flipped = [round(-v, 3) + 0.0 for v in normal] if votes > 0 else hole["normal"]
    return {**hole, "normal": flipped, "thickness": reveal}


def main() -> None:
    args = sys.argv[sys.argv.index("--") + 1 :]
    src, seeds_path, out = Path(args[0]), Path(args[1]), Path(args[2])
    seeds = json.loads(seeds_path.read_text())
    houses = args[3:] or list(seeds)
    result = json.loads(out.read_text()) if out.exists() else {}
    for house in houses:
        rooms = load_bvh(src / f"{house}int.dff")[0]
        bvh, lo, hi = load_bvh(src / f"{house}.dff")
        mapped = [(Vector(s["centre"]), Vector((1, 0, 0)) if s["normal"] == "x" else Vector((0, 1, 0)), "map") for s in seeds[house]["windows"]]
        scanned = [(c, n, "scan") for c, n in scan(bvh, lo, hi)]
        openings = []
        for centre, normal, source in mapped + scanned:
            hole = fit(bvh, centre, normal)
            if not hole or (source == "scan" and (hole["height"] > MAX_WINDOW[1] or hole["open_cells"] < 0.99 * hole["cells"] or holds_door(hole, seeds[house]["doors"]))):
                continue
            if not any((Vector(hole["centre"]) - Vector(o["centre"])).length < 0.3 for o in openings):
                openings.append({**outward(rooms, hole), "source": source})
        result[house] = openings
        print(f"{house}: {len(mapped)} map seeds, {len(scanned)} scanned -> {len(openings)} openings ({sum(o['source'] == 'scan' for o in openings)} from the scan)")
        for o in openings:
            print(f"   {o}")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1) + "\n")


main()
