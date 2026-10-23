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
    if "--without-panes" in sys.argv:
        # one suppression per 300 m cell that holds a window001; a 250 m radius (Ariane's cap) covers the cell
        cells = set()
        for line in (game / "scavenge" / "scavenge.ipl").read_text().splitlines():
            if line.startswith("19466,"):
                f = line.split(",")
                cells.add((round(float(f[3]) / 300), round(float(f[4]) / 300)))
        jobs += [(x * 300, y * 300, 250, 19466) for x, y in sorted(cells)]
        print(f"hiding window001 in {len(cells)} cells")
    failed = 0
    for job in jobs:
        try:
            client.command("suppress_world_models", *job)
        except Exception as error:  # report and keep going: one bad removal should not leave the rest unapplied
            failed += 1
            print(f"failed {job}: {error}")
    print(f"{len(jobs)} suppressions, {failed} failed")


if __name__ == "__main__":
    main()
