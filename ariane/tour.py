"""Fly the running Ariane round one placed instance of each shell and capture it from two opposite corners.

usage (set the time first with ctl.ps1 environment): <ariane-agent venv python> ariane/tour.py <scavenge.ipl> <out dir> [house ...]

Used to spot openings that still have no glass. Captures land in <out dir>/<house>-a.png and -b.png.
"""

import math
import sys
import time
from pathlib import Path

from ariane_agent_tools.ariane_ipc import ArianeClient

HOUSES = [f"{zone}house{i}" for zone in ("ls", "sf", "lv") for i in range(1, 5)]


def main() -> None:
    ipl, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    first = {}
    for line in ipl.read_text().splitlines():
        p = [s.strip() for s in line.split(",")]
        if len(p) == 11 and p[1].lower() in HOUSES and p[1].lower() not in first:
            first[p[1].lower()] = tuple(map(float, p[3:10]))
    client = ArianeClient()
    for house in sys.argv[3:] or HOUSES:
        x, y, z, _, _, qz, qw = first[house]
        yaw = 2 * math.atan2(-qz, qw)  # IPL stores the inverse rotation
        for tag, corner in (("a", 0.6), ("b", 0.6 + math.pi)):
            a = yaw + corner
            eye = (x + 22 * math.cos(a), y + 22 * math.sin(a), z + 9)
            client.command("camera", *[round(c, 2) for c in (*eye, x, y, z)], 60)
            time.sleep(0.8)
            client.capture_current(str((out / f"{house}-{tag}.png").resolve()))
        print(f"{house} at {x:.0f}, {y:.0f}")


if __name__ == "__main__":
    main()
