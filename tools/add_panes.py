"""Glaze the shell exteriors: build a window into every opening in data/windows.json, so maps no longer need window001.

usage: python tools/add_panes.py <DragonFF checkout> <original dir> <windows.json> <out dir> [house ...]

Works on the RenderWare data directly (gtaLib), so the rest of each exterior stays exactly as SA-MP shipped it. The
exteriors use vanilla TXDs, which have no glass, frame or fabric textures, so every new material is untextured and the
detail lives in vertex colours (day and night prelight), which SA lerps per vertex:

- the opening is lined (the reveal, measured against the interior model) and gets a sill that stands out of the wall;
- the glass sits half way into the reveal, subdivided so it can carry a sky-to-street gradient, a soft diagonal
  reflection band and darker edges, after vanilla's see-through glass (dark prelight, about 35);
- frames are boxes standing proud of the glass, shaded like the game would light them (lit tops, dark undersides),
  styled per house after the window texture in its vanilla TXD (STYLES);
- behind the glass, each window gets curtains, a part-lowered blind or nothing, picked with a fixed seed per window, in
  the palette of its district, with folds and slats painted in the vertex colours.

Every new face is emitted with both windings, so it shows from either side whatever the culling.
"""

import json
import math
import random
import sys
from pathlib import Path

GLASS = (150, 168, 176, 170)  # material colour and alpha; prelight below sets the brightness
GLASS_DAY = ((30, 33, 35), (58, 64, 72))  # bottom and top of the pane (SA doubles prelight)
GLASS_NIGHT = ((13, 14, 17), (24, 26, 32))
SHEEN = ((44, 46, 48), (7, 7, 9))  # added along the reflection band, day and night
LIT, NIGHT_FACTOR = 96 / 255, 0.23  # prelight of a lit face as a fraction of the material colour; night = day x this
SHADE = {"front": 1.0, "top": 1.15, "bottom": 0.55, "side": 0.8}  # fake light on box faces
OVERLAP = 0.02  # metres the glass reaches past its opening, so no light leaks at the edges
FRAME_DEPTH = 0.045  # how far frames stand out of the glass
SILL = {"drop": 0.06, "proud": 0.07, "wider": 0.08}  # sill height, how far it sticks out of the wall, overhang per side
CURTAIN_GAP = 0.08  # curtains hang this far inside the inner wall face
# Frame per house, after the window texture of its vanilla TXD. colour: frame material colour; trim: sill and reveal;
# border, bar: widths in metres; columns: "auto" (a centre mullion on openings wider than 1.3 m), ("split", n) equal
# panes, ("every", m) a bar every m metres, or None; rows: heights (0..1 from the bottom) of horizontal bars, row_bar
# their width; fabric: the district's curtain and blind colours.
SF_FABRIC = [(226, 214, 186), (205, 196, 176), (150, 62, 52), (120, 132, 150)]
LS_FABRIC = [(198, 162, 112), (154, 172, 190), (212, 202, 172), (170, 120, 90)]
LV_FABRIC = [(232, 226, 210), (204, 188, 152), (182, 202, 200), (226, 220, 200)]
SASH = {"colour": (232, 230, 222), "trim": (214, 210, 200), "border": 0.07, "bar": 0.035, "columns": ("every", 0.75), "rows": [0.5], "row_bar": 0.07, "fabric": SF_FABRIC}  # ws_boxhouse_wins5/7
WOOD = {"colour": (176, 150, 116), "trim": (150, 132, 110), "border": 0.08, "bar": 0.05, "columns": "auto", "rows": [0.7], "row_bar": 0.05, "fabric": LS_FABRIC}  # gangwin1_LAe
STYLES = {
    **{f"sfhouse{i}": SASH for i in range(1, 5)},
    "lshouse1": WOOD,
    "lshouse2": WOOD,
    "lshouse3": {"colour": (176, 178, 176), "trim": (190, 188, 182), "border": 0.04, "bar": 0.03, "columns": None, "rows": [i / 7 for i in range(1, 7)], "row_bar": 0.03, "fabric": LS_FABRIC},  # comptwindo1 louvres
    "lshouse4": {"colour": (62, 62, 60), "trim": (205, 205, 198), "border": 0.06, "bar": 0.04, "columns": ("split", 2), "rows": [0.5], "row_bar": 0.04, "fabric": LS_FABRIC},  # ws_boxhouse_wins3
    "lvhouse1": {"colour": (214, 218, 214), "trim": (196, 188, 176), "border": 0.05, "bar": 0.022, "columns": ("every", 0.12), "rows": [0.12, 0.88], "row_bar": 0.03, "fabric": LV_FABRIC},  # comptwindo4 security bars
    "lvhouse2": {"colour": (52, 70, 150), "trim": (208, 204, 196), "border": 0.07, "bar": 0.05, "columns": ("split", 2), "rows": [0.6], "row_bar": 0.05, "fabric": LV_FABRIC},  # newindow10
    "lvhouse3": {"colour": (138, 142, 140), "trim": (200, 196, 186), "border": 0.06, "bar": 0.04, "columns": ("every", 0.8), "rows": [], "row_bar": 0.04, "fabric": LV_FABRIC},  # sw_wind10
    "lvhouse4": {"colour": (200, 202, 204), "trim": (222, 214, 200), "border": 0.04, "bar": 0.035, "columns": ("split", 2), "rows": [], "row_bar": 0.035, "fabric": LV_FABRIC},  # comptwindo4, sliders
}


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


def scale(colour, k: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, round(c * k))) for c in colour)


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
        # frames and trim carry their colour in the material and their shading in the prelight; fabric is white and
        # takes its colour from the prelight, so one material serves every curtain
        glass = untextured(geometry, GLASS)
        frame = untextured(geometry, (*style["colour"], 255))
        trim = untextured(geometry, (*style["trim"], 255))
        fabric = untextured(geometry, (255, 255, 255, 255))
        night_colours = geometry.extensions["extra_vert_color"].colors
        has_normals = len(geometry.normals) > 0  # SA-MP's exteriors have none; adding some would set the flag

        def face(corners, day, night, material) -> None:
            """A quad from 4 corners with per-corner day and night colours, emitted with both windings."""
            base = len(geometry.vertices)
            for (x, y, z), d, n, uv in zip(corners, day, night, ((0, 1), (1, 1), (1, 0), (0, 0))):
                geometry.vertices.append(dff.Vector(x, y, z))
                if has_normals:
                    geometry.normals.append(dff.Vector(0, 0, 1))
                geometry.prelit_colors.append(dff.RGBA(*d, 255))
                night_colours.append(dff.RGBA(*n, 255))
                for layer in geometry.uv_layers:
                    layer.append(dff.TexCoords(*uv))
            for a, b, c in ((0, 1, 2), (0, 2, 3), (0, 2, 1), (0, 3, 2)):
                geometry.triangles.append(dff.Triangle(b=base + b, a=base + a, material=material, c=base + c))

        for index, opening in enumerate(windows[house]):
            rng = random.Random(f"{house}:{index}")
            c = opening["centre"]
            n = opening["normal"]  # out of the house
            t = (-n[1], n[0])  # along the wall
            hw, hh = opening["width"] / 2, opening["height"] / 2
            reveal = max(opening.get("thickness", 0.1), 0.05)

            def at(u: float, v: float, d: float) -> tuple[float, float, float]:
                """Point u along the wall, v up and d out of the house from the opening centre (on the outer wall face)."""
                return (c[0] + t[0] * u + n[0] * d, c[1] + t[1] * u + n[1] * d, c[2] + v)

            def box(u0, v0, u1, v1, d0, d1, light, material) -> None:
                """Five faces of a box from depth d0 (back, not drawn) to d1 (front), shaded by which way each faces.
                light: prelight of a lit face, as a fraction (the material colour carries the hue)."""

                def shade(kind):
                    day = scale((255, 255, 255), light * SHADE[kind])
                    return [day] * 4, [scale(day, NIGHT_FACTOR)] * 4

                face([at(u0, v0, d1), at(u1, v0, d1), at(u1, v1, d1), at(u0, v1, d1)], *shade("front"), material)
                face([at(u0, v1, d1), at(u1, v1, d1), at(u1, v1, d0), at(u0, v1, d0)], *shade("top"), material)
                face([at(u0, v0, d0), at(u1, v0, d0), at(u1, v0, d1), at(u0, v0, d1)], *shade("bottom"), material)
                face([at(u0, v0, d0), at(u0, v0, d1), at(u0, v1, d1), at(u0, v1, d0)], *shade("side"), material)
                face([at(u1, v0, d1), at(u1, v0, d0), at(u1, v1, d0), at(u1, v1, d1)], *shade("side"), material)

            def grid(u0, v0, u1, v1, d, nu, nv, colour, material) -> None:
                """A flat panel split into nu x nv cells; colour(s, t) -> (day, night) at each grid point (0..1)."""
                for i in range(nu):
                    for j in range(nv):
                        pts = [(i / nu, j / nv), ((i + 1) / nu, j / nv), ((i + 1) / nu, (j + 1) / nv), (i / nu, (j + 1) / nv)]
                        cols = [colour(s, tt) for s, tt in pts]
                        corners = [at(u0 + (u1 - u0) * s, v0 + (v1 - v0) * tt, d) for s, tt in pts]
                        face(corners, [x[0] for x in cols], [x[1] for x in cols], material)

            # the reveal, lined from the outer wall face to the inner one (darker deeper in), and a sill below it
            box(-hw, -hh - SILL["drop"], hw, -hh, -reveal, 0, LIT * 0.75, trim)
            box(-hw - 0.01, -hh, -hw, hh, -reveal, 0, LIT * 0.6, trim)
            box(hw, -hh, hw + 0.01, hh, -reveal, 0, LIT * 0.6, trim)
            box(-hw, hh, hw, hh + 0.01, -reveal, 0, LIT * 0.45, trim)
            box(-hw - SILL["wider"], -hh - SILL["drop"], hw + SILL["wider"], -hh, -0.01, SILL["proud"], LIT, trim)

            # the glass, half way into the reveal
            glass_d = -reveal / 2
            band, tint = rng.uniform(0.3, 0.75), rng.uniform(0.9, 1.1)

            def glass_colour(s: float, tt: float):
                sheen = math.exp(-(((s * 0.7 + tt) / 1.7 - band) / 0.11) ** 2)
                edge = 0.82 if min(s, tt, 1 - s, 1 - tt) < 0.01 else 1.0
                day = [(lo + (hi - lo) * tt) * tint * edge + sheen * add for lo, hi, add in zip(*GLASS_DAY, SHEEN[0])]
                night = [(lo + (hi - lo) * tt) * edge + sheen * add for lo, hi, add in zip(*GLASS_NIGHT, SHEEN[1])]
                return scale(day, 1), scale(night, 1)

            nu, nv = max(2, round(opening["width"] / 0.35)), max(2, round(opening["height"] / 0.35))
            grid(-hw - OVERLAP, -hh - OVERLAP, hw + OVERLAP, hh + OVERLAP, glass_d, nu, nv, glass_colour, glass)

            # the frame, standing out of the glass
            for u0, v0, u1, v1 in frame_bars(style, opening["width"], opening["height"]):
                box(u0, v0, u1, v1, glass_d, glass_d + FRAME_DEPTH, LIT, frame)

            # behind the glass: curtains, a blind or nothing
            colour = rng.choice(style["fabric"])
            hang = -reveal - CURTAIN_GAP
            kind = rng.random()
            if kind < 0.4:
                folds = rng.randint(5, 8)

                def cloth(s: float, tt: float):
                    k = 1.0 if round(s * folds * 2) % 2 == 0 else 0.74
                    return scale(colour, 0.5 * k), scale(colour, 0.11 * k)

                for side in (-1, 1):
                    width = opening["width"] * rng.uniform(0.18, 0.32)
                    u0, u1 = sorted((side * (hw + 0.1), side * (hw - width)))
                    grid(u0, -hh - 0.1, u1, hh + 0.12, hang, folds * 2, 1, cloth, fabric)
            elif kind < 0.72:
                drop = opening["height"] * rng.uniform(0.2, 0.6)
                slats = max(4, round(drop / 0.07))

                def blind(s: float, tt: float):
                    k = 1.0 if round(tt * slats) % 2 == 0 else 0.84
                    return scale(colour, 0.5 * k), scale(colour, 0.11 * k)

                grid(-hw - 0.05, hh - drop, hw + 0.05, hh + 0.05, hang, 1, slats, blind, fabric)
        model.write_file(str(out / f"{house}.dff"), 0x36003)
        print(f"{house}: {len(windows[house])} windows -> {out / f'{house}.dff'}")


if __name__ == "__main__":
    main()
