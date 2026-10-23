"""Point the running Ariane camera at a placed model's largest face, from the side that face looks at.

usage: <ariane-agent venv python> ariane/look_at.py <game dir> <model id> <dff> [distance] [instance]

Used to look at vanilla references (glass, windows) without guessing which way a building faces: the face normal
comes from the DFF, the rotation from the model's IPL placement (text IPLs and the binary ones in gta3.img).
"""

import math
import struct
import sys
from pathlib import Path

sys.path.insert(0, r"C:\dev\gta\sa\tools\DragonFF")
from ariane_agent_tools.ariane_ipc import ArianeClient  # noqa: E402
from gtaLib import dff  # noqa: E402


def placements(game: Path, model: int) -> list[tuple[float, ...]]:
    """(x, y, z, qx, qy, qz, qw) for every placement of the model; IPLs store the inverse rotation."""
    found = []
    for ipl in (game / "data" / "maps").rglob("*.ipl"):
        inst = False
        for line in ipl.read_text(errors="ignore").splitlines():
            line = line.split("#")[0].strip()
            if line.lower() in ("inst", "end"):
                inst = line.lower() == "inst"
            elif inst and line:
                p = [s.strip() for s in line.split(",")]
                if int(p[0]) == model:
                    found.append(tuple(map(float, p[3:10])))
    img = (game / "models" / "gta3.img").read_bytes()
    for i in range(struct.unpack_from("<I", img, 4)[0]):
        offset, size, _, name = struct.unpack_from("<IHH24s", img, 8 + i * 32)
        blob = img[offset * 2048 : (offset + size) * 2048]
        if name.split(b"\0")[0].lower().endswith(b".ipl") and blob[:4] == b"bnry":
            count, at = struct.unpack_from("<I", blob, 4)[0], struct.unpack_from("<I", blob, 0x1C)[0]
            for k in range(count):
                *pose, m = struct.unpack_from("<7fi", blob, at + k * 40)
                if m == model:
                    found.append(tuple(pose))
    return found


def rotate(q: tuple[float, float, float, float], v: tuple[float, float, float]) -> tuple[float, float, float]:
    qx, qy, qz, qw = -q[0], -q[1], -q[2], q[3]  # undo the IPL inversion
    x, y, z = v
    tx, ty, tz = 2 * (qy * z - qz * y), 2 * (qz * x - qx * z), 2 * (qx * y - qy * x)
    return (x + qw * tx + qy * tz - qz * ty, y + qw * ty + qz * tx - qx * tz, z + qw * tz + qx * ty - qy * tx)


def largest_face(path: Path) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    model = dff.dff()
    model.load_file(str(path))
    best = (0.0, None, None)
    for geometry in (g for c in model.clumps for g in c.geometry_list):
        v = geometry.vertices
        for t in geometry.triangles:
            a, b, c = v[t.a], v[t.b], v[t.c]
            u, w = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
            n = (u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0])
            area = math.sqrt(sum(x * x for x in n)) / 2
            if area > best[0]:
                centre = tuple((a[i] + b[i] + c[i]) / 3 for i in range(3))
                best = (area, centre, tuple(x / (2 * area) for x in n))
    return best[1], best[2]


def main() -> None:
    game, model, path = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
    distance = float(sys.argv[4]) if len(sys.argv) > 4 else 12.0
    x, y, z, *q = placements(game, model)[int(sys.argv[5]) if len(sys.argv) > 5 else 0]
    centre, normal = largest_face(path)
    cx, cy, cz = (a + b for a, b in zip((x, y, z), rotate(q, centre)))
    nx, ny, nz = rotate(q, normal)
    eye = (cx + nx * distance, cy + ny * distance, cz + nz * distance + 1.5)
    ArianeClient().command("camera", *[round(c, 2) for c in (*eye, cx, cy, cz)], 60)
    print(f"camera {eye} -> {(cx, cy, cz)}")


if __name__ == "__main__":
    main()
