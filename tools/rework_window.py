"""Rework SA-MP's window pane (19466 window001) and its glass texture (lsmall_window01 in lsmall_shops.txd).

usage: python tools/rework_window.py <DragonFF checkout> <original dir> <out dir>   (run from the repo root)

window001 has the same fault as the house interiors had: no prelight and a grey 127 material, so the game lights
it like a dynamic object and the pane glows at night. It gets uniform day/night prelight (dark glass after dusk) and
a white material. The texture, a flat 16x16 grey at alpha 212, becomes a 64x64 glass pane: a sky-to-ground gradient
with two soft reflection streaks, transparent enough to show the room behind it. The texture is shared with 19325
lsmall_window01 (shop glass), which benefits the same way.
"""

import math
import sys
from pathlib import Path

DAY = (128, 128, 128)  # SA doubles prelight: 128 shows the texture as painted
NIGHT = (30, 33, 40)  # dark glass with a little sky blue, about the night level of the walls around it
SIZE = 64
TOP, BOTTOM = (150, 170, 186), (84, 98, 112)  # reflected sky above, darker street below
ALPHA = 150  # the original's 212 reads as a grey board
STREAKS = ((0.30, 0.10, 46), (0.58, 0.05, 30))  # (centre along the diagonal, half width, brightness)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def glass_pixels() -> bytes:
    """RGBA rows, top row first."""
    out = bytearray()
    for y in range(SIZE):
        v = y / (SIZE - 1)
        for x in range(SIZE):
            u = x / (SIZE - 1)
            d = (u + v) / 2  # position along the 45 degree diagonal
            glow = sum(b * math.exp(-(((d - c) / w) ** 2)) for c, w, b in STREAKS)
            edge = min(x, y, SIZE - 1 - x, SIZE - 1 - y)
            shade = 0.8 if edge < 2 else 1.0  # a thin darker rim where the pane meets the frame
            rgb = [min(255, round(lerp(t, b, v) * shade + glow)) for t, b in zip(TOP, BOTTOM)]
            out += bytes((*rgb, min(255, round(ALPHA + glow * 0.8 + (40 if edge < 2 else 0)))))
    return bytes(out)


def main() -> None:
    dragonff, src, out = (Path(p) for p in sys.argv[1:4])
    sys.path.insert(0, str(dragonff))
    from gtaLib import dff, txd

    out.mkdir(parents=True, exist_ok=True)
    model = dff.dff()
    model.load_file(str(src / "window001.dff"))
    for clump in model.clumps:
        for geometry in clump.geometry_list:
            count = len(geometry.vertices)
            # gtaLib reads the BinMesh into a plain list it cannot write back; its triangles carry the real
            # material ids (SA-MP's triangle list says 0), and the writer rebuilds the BinMesh from them
            geometry.triangles = geometry.extensions.pop("mat_split", None) or geometry.triangles
            geometry.export_flags["modulate_color"] = bool(geometry.flags & 0x40)
            geometry.prelit_colors = [dff.RGBA(*DAY, 255)] * count
            geometry.extensions["extra_vert_color"] = dff.ExtraVertColorExtension([dff.RGBA(*NIGHT, 255)] * count)
            for material in geometry.materials:
                material.color = dff.RGBA(255, 255, 255, material.color.a)
    model.write_file(str(out / "window001.dff"), 0x36003)

    textures = txd.txd()
    textures.load_file(str(src / "lsmall_shops.txd"))
    pane = next(t for t in textures.native_textures if t.name == "lsmall_window01")
    pane.width = pane.height = SIZE
    pane.pixels = [txd.ImageEncoder.rgba_to_bgra8888(glass_pixels())]
    textures.write_file(str(out / "lsmall_shops.txd"), textures.version if hasattr(textures, "version") else 0x36003)
    print(f"wrote {out / 'window001.dff'} and {out / 'lsmall_shops.txd'}")


if __name__ == "__main__":
    main()
