"""Glaze the shell exteriors: add a framed pane to every opening in data/windows.json, so maps no longer need window001.

usage: python tools/add_panes.py <DragonFF checkout> <original dir> <windows.json> <out dir> [house ...]

Works on the RenderWare data directly (gtaLib), so the rest of each exterior stays exactly as SA-MP shipped it. The
exteriors use vanilla TXDs, which have no glass texture, so both new materials are untextured and the look comes from
vertex colours, after vanilla's see-through glass (e.g. carshowwin_SFSX): dark prelight around 35, so the pane reads as
glass with the room behind it, graded lighter towards the top like a sky reflection. A frame sits just in front of the
glass on both faces, styled per house after the window texture in its vanilla TXD (STYLES): white sashes on the SF row
houses, weathered wood in Ganton, aluminium louvres on the LS cabin, security bars on the LV ghetto house, and so on.
"""

import json
import sys
from pathlib import Path

GLASS = (150, 168, 176, 170)  # material colour and alpha; prelight below sets the brightness
GLASS_DAY = ((30, 33, 35), (54, 60, 68))  # bottom and top of the pane (SA doubles prelight)
GLASS_NIGHT = ((14, 15, 18), (24, 26, 32))
FRAME_DAY, FRAME_NIGHT = (96, 95, 92), (22, 22, 22)
OVERLAP = 0.02  # metres each pane reaches past its opening, so no light leaks at the edges
# Frame per house, after the window texture of its vanilla TXD. colour: material colour; border, bar: widths in metres;
# columns: "auto" (a centre mullion on openings wider than 1.3 m), ("split", n) equal panes, ("every", m) a bar every m
# metres, or None; rows: heights (0..1 from the bottom) of horizontal bars, with their own width row_bar.
SASH = {"colour": (232, 230, 222), "border": 0.07, "bar": 0.035, "columns": ("every", 0.75), "rows": [0.5], "row_bar": 0.07}  # ws_boxhouse_wins5/7
WOOD = {"colour": (176, 150, 116), "border": 0.08, "bar": 0.05, "columns": "auto", "rows": [0.7], "row_bar": 0.05}  # gangwin1_LAe
STYLES = {
    **{f"sfhouse{i}": SASH for i in range(1, 5)},
    "lshouse1": WOOD,
    "lshouse2": WOOD,
    "lshouse3": {"colour": (176, 178, 176), "border": 0.04, "bar": 0.03, "columns": None, "rows": [i / 7 for i in range(1, 7)], "row_bar": 0.03},  # comptwindo1 louvres
    "lshouse4": {"colour": (62, 62, 60), "border": 0.06, "bar": 0.04, "columns": ("split", 2), "rows": [0.5], "row_bar": 0.04},  # ws_boxhouse_wins3
    "lvhouse1": {"colour": (214, 218, 214), "border": 0.05, "bar": 0.022, "columns": ("every", 0.12), "rows": [0.12, 0.88], "row_bar": 0.03},  # comptwindo4 security bars
    "lvhouse2": {"colour": (52, 70, 150), "border": 0.07, "bar": 0.05, "columns": ("split", 2), "rows": [0.6], "row_bar": 0.05},  # newindow10
    "lvhouse3": {"colour": (138, 142, 140), "border": 0.06, "bar": 0.04, "columns": ("every", 0.8), "rows": [], "row_bar": 0.04},  # sw_wind10
    "lvhouse4": {"colour": (200, 202, 204), "border": 0.04, "bar": 0.035, "columns": ("split", 2), "rows": [], "row_bar": 0.035},  # comptwindo4, sliders
}
FRAME_OFFSET = 0.012  # frame quads sit this far in front of the glass, on each face


def frame_bars(style: dict, width: float, height: float) -> list[tuple[float, float, float, float]]:
    """Frame rectangles (u0, v0, u1, v1) around the opening centre: the border, then the style's columns and rows."""
    hw, hh, border, bar = width / 2, height / 2, style["border"], style["bar"]
    bars = [(-hw, -hh, hw, -hh + border), (-hw, hh - border, hw, hh), (-hw, -hh, -hw + border, hh), (hw - border, -hh, hw, hh)]
    columns = style["columns"]
    if columns == "auto":
        panes = 2 if width > 1.3 else 1
    elif columns and columns[0] == "split":
        panes = columns[1]
    elif columns and columns[0] == "every":
        panes = max(1, round(width / columns[1]))
    else:
        panes = 1
    for k in range(1, panes):
        u = -hw + width * k / panes
        bars.append((u - bar / 2, -hh, u + bar / 2, hh))
    for f in style["rows"]:
        v = -hh + height * f
        bars.append((-hw, v - style["row_bar"] / 2, hw, v + style["row_bar"] / 2))
    return bars


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
        style = STYLES[house]
        glass, frame = untextured(geometry, GLASS), untextured(geometry, (*style["colour"], 255))
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
            bars = frame_bars(style, opening["width"], opening["height"])
            for side in (1, -1):
                quad((cx, cy, cz), tangent, (nx, ny), (-hw - OVERLAP, -hh - OVERLAP, hw + OVERLAP, hh + OVERLAP), side, glass, GLASS_DAY, GLASS_NIGHT)
                front = (cx + nx * side * FRAME_OFFSET, cy + ny * side * FRAME_OFFSET, cz)
                for bar in bars:
                    quad(front, tangent, (nx, ny), bar, side, frame, (FRAME_DAY, FRAME_DAY), (FRAME_NIGHT, FRAME_NIGHT))
        model.write_file(str(out / f"{house}.dff"), 0x36003)
        print(f"{house}: {len(windows[house])} framed panes -> {out / f'{house}.dff'}")


if __name__ == "__main__":
    main()
