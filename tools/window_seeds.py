"""Find where servers put window panes in each shell, as seeds for tools/glaze_shells.py.

usage: python tools/window_seeds.py <scavenge.ipl from make_ipl.py> data/window_seeds.json

The shells ship with open window holes, so maps fill them with SA-MP's 19466 window001, one object per hole (1643 in
Scavenge & Survive). Every window001 within 20 m of a shell is moved into that shell's local frame; offsets that recur
in at least half of a shell type's instances are the holes. Only the rough centre and facing are kept: the glazing
tool fits the actual opening from the geometry. Door objects (any model named *door*) are collected the same way, so
the glazing tool's own scan never puts glass across an entrance.
"""

import collections
import json
import math
import sys
from pathlib import Path

HOUSES = [f"{zone}house{i}" for zone in ("sf", "lv", "ls") for i in range(1, 5)]


def yaw(qx: float, qy: float, qz: float, qw: float) -> float | None:
    """IPL quaternions are stored inverted; None for anything that is not a pure z rotation."""
    if abs(qx) > 1e-3 or abs(qy) > 1e-3:
        return None
    return math.degrees(2 * math.atan2(-qz, qw))


def main() -> None:
    ipl, out = Path(sys.argv[1]), Path(sys.argv[2])
    rows = []
    for line in ipl.read_text().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) == 11 and parts[0].isdigit():
            rows.append((parts[1].lower(), *map(float, parts[3:10])))
    panes = [r for r in rows if r[0] == "window001" and yaw(*r[4:]) is not None]
    doors = [r for r in rows if "door" in r[0] and yaw(*r[4:]) is not None]
    seeds = {}
    for house in HOUSES:
        instances = [r for r in rows if r[0] == house and yaw(*r[4:]) is not None]
        offsets, door_offsets = collections.Counter(), collections.Counter()
        for _, hx, hy, hz, *q in instances:
            angle = math.radians(-yaw(*q))
            c, s = math.cos(angle), math.sin(angle)
            for found, objects in ((offsets, panes), (door_offsets, doors)):
                for _, wx, wy, wz, *wq in objects:
                    dx, dy, dz = wx - hx, wy - hy, wz - hz
                    if dx * dx + dy * dy < 400 and abs(dz) < 12:
                        facing = round((yaw(*wq) - yaw(*q)) % 180)
                        found[(round(dx * c - dy * s, 1), round(dx * s + dy * c, 1), round(dz, 1), facing)] += 1
        keep = max(2, len(instances) // 2)
        seeds[house] = {
            "windows": [{"centre": list(k[:3]), "normal": "x" if k[3] == 0 else "y", "seen": n} for k, n in sorted(offsets.items()) if n >= keep],
            "doors": [{"centre": list(k[:3]), "seen": n} for k, n in sorted(door_offsets.items()) if n >= keep],
        }
        print(f"{house}: {len(instances)} instances, {len(seeds[house]['windows'])} window seeds, {len(seeds[house]['doors'])} doors")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(seeds, indent=1) + "\n")


if __name__ == "__main__":
    main()
