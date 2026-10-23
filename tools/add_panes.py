"""Glaze the shell exteriors: add a framed pane to every opening in data/windows.json, so maps no longer need window001.

usage: python tools/add_panes.py <DragonFF checkout> <original dir> <windows.json> <out dir> [house ...]

Works on the RenderWare data directly (gtaLib), so the rest of each exterior stays exactly as SA-MP shipped it. The
exteriors use vanilla TXDs, which have no glass texture, so both new materials are untextured and the look comes from
vertex colours, after vanilla's see-through glass (e.g. carshowwin_SFSX): dark prelight around 35, so the pane reads as
glass with the room behind it, graded lighter towards the top like a sky reflection. A painted frame (border, centre
mullion on wide openings, transom on tall ones) sits just in front of the glass on both faces.
"""

import json
import sys
from pathlib import Path

GLASS = (150, 168, 176, 170)  # material colour and alpha; prelight below sets the brightness
GLASS_DAY = ((30, 33, 35), (54, 60, 68))  # bottom and top of the pane (SA doubles prelight)
GLASS_NIGHT = ((14, 15, 18), (24, 26, 32))
FRAME = (205, 200, 190, 255)
FRAME_DAY, FRAME_NIGHT = (96, 95, 92), (22, 22, 22)
OVERLAP = 0.02  # metres each pane reaches past its opening, so no light leaks at the edges
BORDER, BAR = 0.06, 0.05  # frame widths
FRAME_OFFSET = 0.012  # frame quads sit this far in front of the glass, on each face


def main() -> None:
    dragonff, src, windows_path, out = (Path(p) for p in sys.argv[1:5])
    sys.path.insert(0, str(dragonff))
    from gtaLib import dff

    def untextured(geometry, colour) -> int:
        material = dff.Material()
        material.flags, material.is_textured, material.textures, material.plugins = 0, 0, [], {}
        material.color = dff.RGBA(*colour)
        material.surface_properties = geometry.materials[0].surface_properties
        geometry.materials.append(material)
        return len(geometry.materials) - 1

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
        glass, frame = untextured(geometry, GLASS), untextured(geometry, FRAME)
        night = geometry.extensions["extra_vert_color"].colors
        has_normals = len(geometry.normals) > 0  # SA-MP's exteriors have none; adding some would set the flag

        def quad(origin, tangent, normal, rect, side, material, day, dark) -> None:
            """rect = (u0, v0, u1, v1) in metres from origin along the wall and up; day/dark = (bottom, top) colours."""
            u0, v0, u1, v1 = rect
            base = len(geometry.vertices)
            for u, v in ((u0, v0), (u1, v0), (u1, v1), (u0, v1)):
                t = 1 if v == v1 else 0
                geometry.vertices.append(dff.Vector(origin[0] + tangent[0] * u, origin[1] + tangent[1] * u, origin[2] + v))
                if has_normals:
                    geometry.normals.append(dff.Vector(normal[0] * side, normal[1] * side, 0))
                geometry.prelit_colors.append(dff.RGBA(*day[t], 255))
                night.append(dff.RGBA(*dark[t], 255))
                for layer in geometry.uv_layers:
                    layer.append(dff.TexCoords((u - u0) / (u1 - u0), 1 - (v - v0) / (v1 - v0)))
            for a, b, c in ((0, 1, 2), (0, 2, 3)) if side == 1 else ((0, 2, 1), (0, 3, 2)):
                geometry.triangles.append(dff.Triangle(b=base + b, a=base + a, material=material, c=base + c))

        for opening in windows[house]:
            cx, cy, cz = opening["centre"]
            nx, ny, _ = opening["normal"]
            tangent = (-ny, nx)  # along the wall: up x normal
            hw, hh = opening["width"] / 2, opening["height"] / 2
            bars = [(-hw, -hh, hw, -hh + BORDER), (-hw, hh - BORDER, hw, hh), (-hw, -hh, -hw + BORDER, hh), (hw - BORDER, -hh, hw, hh)]
            if opening["width"] > 1.3:
                bars.append((-BAR / 2, -hh, BAR / 2, hh))
            if opening["height"] > 1.2:
                transom = hh - opening["height"] * 0.3
                bars.append((-hw, transom - BAR / 2, hw, transom + BAR / 2))
            for side in (1, -1):
                quad((cx, cy, cz), tangent, (nx, ny), (-hw - OVERLAP, -hh - OVERLAP, hw + OVERLAP, hh + OVERLAP), side, glass, GLASS_DAY, GLASS_NIGHT)
                front = (cx + nx * side * FRAME_OFFSET, cy + ny * side * FRAME_OFFSET, cz)
                for bar in bars:
                    quad(front, tangent, (nx, ny), bar, side, frame, (FRAME_DAY, FRAME_DAY), (FRAME_NIGHT, FRAME_NIGHT))
        model.write_file(str(out / f"{house}.dff"), 0x36003)
        print(f"{house}: {len(windows[house])} framed panes -> {out / f'{house}.dff'}")


if __name__ == "__main__":
    main()
