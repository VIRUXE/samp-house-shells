"""Send every world-model suppression to the running Ariane from one process (one arianectl call each took minutes).

usage: <ariane-agent venv python> ariane/removals.py <game dir> [--without-panes]   (called by apply-removals.ps1)
"""

import json
import sys
from pathlib import Path

from ariane_agent_tools.ariane_ipc import ArianeClient


def main() -> None:
    game = Path(sys.argv[1])
    client = ArianeClient()
    jobs = [(r["x"], r["y"], r["radius"], r["model"]) for r in json.loads((game / "scavenge" / "removals.json").read_text()) if r["model"] >= 0]
    failed = 0
    for job in jobs:
        try:
            client.command("suppress_world_models", *job)
        except Exception as error:  # report and keep going: one bad removal should not leave the rest unapplied
            failed += 1
            print(f"failed {job}: {error}")
    print(f"{len(jobs)} removals, {failed} failed")
    if "--without-panes" in sys.argv:
        panes = []
        for line in (game / "scavenge" / "scavenge.ipl").read_text().splitlines():
            if line.startswith("19466,"):
                f = line.split(",")
                panes.append((float(f[3]), float(f[4])))
        print(f"hiding {len(panes)} window001 in {hide(client, panes, 0, 0, 6000)} zones")


def hide(client: ArianeClient, panes: list[tuple[float, float]], x: float, y: float, size: float) -> int:
    """Suppress window001 in the square cell centred on x, y; split it while it is over Ariane's caps
    (250 m radius, 256 matched instances). Returns the number of zones used."""
    inside = [p for p in panes if abs(p[0] - x) <= size / 2 and abs(p[1] - y) <= size / 2]
    if not inside:
        return 0
    if size <= 340:  # half-diagonal under 250 m
        try:
            client.command("suppress_world_models", x, y, round(size * 0.71 + 1, 1), 19466)
            return 1
        except Exception as error:
            if "more than" not in str(error):
                print(f"failed ({x}, {y}): {error}")
                return 0
    q = size / 4
    return sum(hide(client, inside, x + dx, y + dy, size / 2) for dx in (-q, q) for dy in (-q, q))


if __name__ == "__main__":
    main()
