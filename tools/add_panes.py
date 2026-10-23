"""Glaze the shell exteriors: add a pane to every opening in data/windows.json, so maps no longer need window001.

usage: python tools/add_panes.py <DragonFF checkout> <original dir> <windows.json> <out dir> [house ...]

Works on the RenderWare data directly (gtaLib), so the rest of each exterior stays exactly as SA-MP shipped it. Each
pane is a double-sided quad on one new material. The exteriors use vanilla TXDs, which have no glass texture, so the
material is untextured: its colour and alpha are the glass, its prelight dims it at night like window001's.
"""

import json
import sys
from pathlib import Path

GLASS = (118, 136, 150, 150)  # material colour and alpha: blue-grey sky reflection, the room shows through
DAY = (128, 128, 128)  # SA doubles prelight: 128 shows the material colour as is
NIGHT = (30, 33, 40)
OVERLAP = 0.02  # metres each pane reaches past its opening, so no light leaks at the edges


def main() -> None:
    dragonff, src, windows_path, out = (Path(p) for p in sys.argv[1:5])
    sys.path.insert(0, str(dragonff))
    from gtaLib import dff

    windows = json.loads(windows_path.read_text())
    out.mkdir(parents=True, exist_ok=True)
    for house in sys.argv[5:] or list(windows):
        model = dff.dff()
        model.load_file(str(src / f"{house}.dff"))
        geometry = model.clumps[0].geometry_list[0]
        # gtaLib reads the BinMesh into a plain list it cannot write back; its triangles carry the real material
        # ids (SA-MP's triangle list says 0), and the writer rebuilds the BinMesh from them
        geometry.triangles = geometry.extensions.pop("mat_split", None) or geometry.triangles
        geometry.export_flags["modulate_color"] = bool(geometry.flags & 0x40)
        glass = dff.Material()
        glass.flags, glass.is_textured, glass.textures, glass.plugins = 0, 0, [], {}
        glass.color = dff.RGBA(*GLASS)
        glass.surface_properties = geometry.materials[0].surface_properties
        geometry.materials.append(glass)
        material = len(geometry.materials) - 1
        night = geometry.extensions["extra_vert_color"].colors
        has_normals = len(geometry.normals) > 0  # SA-MP's exteriors have none; adding some would set the flag
        for opening in windows[house]:
            cx, cy, cz = opening["centre"]
            nx, ny, _ = opening["normal"]
            tx, ty = -ny, nx  # along the wall: up x normal
            hw, hh = opening["width"] / 2 + OVERLAP, opening["height"] / 2 + OVERLAP
            corners = [(cx + tx * u * hw, cy + ty * u * hw, cz + v * hh) for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            for side in (1, -1):
                base = len(geometry.vertices)
                for (x, y, z), uv in zip(corners, ((0, 1), (1, 1), (1, 0), (0, 0))):
                    geometry.vertices.append(dff.Vector(x, y, z))
                    if has_normals:
                        geometry.normals.append(dff.Vector(nx * side, ny * side, 0))
                    geometry.prelit_colors.append(dff.RGBA(*DAY, 255))
                    night.append(dff.RGBA(*NIGHT, 255))
                    for layer in geometry.uv_layers:
                        layer.append(dff.TexCoords(*uv))
                quad = ((0, 1, 2), (0, 2, 3)) if side == 1 else ((0, 2, 1), (0, 3, 2))
                for a, b, c in quad:
                    geometry.triangles.append(dff.Triangle(b=base + b, a=base + a, material=material, c=base + c))
        model.write_file(str(out / f"{house}.dff"), 0x36003)
        print(f"{house}: {len(windows[house])} panes -> {out / f'{house}.dff'}")


if __name__ == "__main__":
    main()
