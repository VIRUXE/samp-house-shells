"""Turn the Blender renders in work/renders/ into one before/after image per house: screenshots/houses/<house>.png.

usage: python tools/gallery.py   (run from the repo root, after tools/render_houses.py)

Each image is a 2x2 grid like screenshots/compare: SA-MP's original on the left, this repo's on the right, noon on top
and midnight below. The close-ups go on one sheet, screenshots/houses/details.png.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))  # python -I leaves the script's folder off the path
from compare import BAR, BG, DIM, FG, GAP, font, label  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WIDTH = 760


def main() -> None:
    renders, out = ROOT / "work" / "renders", ROOT / "screenshots" / "houses"
    out.mkdir(parents=True, exist_ok=True)
    for house in sorted({p.name.split("-")[0] for p in renders.glob("*-reworked-noon.png")}):
        paths = {(s, t): renders / f"{house}-{s}-{t}.png" for s in ("original", "reworked") for t in ("noon", "midnight")}
        if not all(p.exists() for p in paths.values()):
            continue
        tiles = {}
        for key, path in paths.items():
            img = Image.open(path).convert("RGB")
            tiles[key] = img.resize((WIDTH, round(img.height * WIDTH / img.width)), Image.LANCZOS)
        h = tiles[("original", "noon")].height
        canvas = Image.new("RGB", (2 * WIDTH + GAP, BAR + 2 * h + GAP), BG)
        draw = ImageDraw.Draw(canvas, "RGBA")
        draw.text((14, 9), house, font=font(22, bold=True), fill=FG)
        draw.text((2 * WIDTH + GAP - 14, 12), "Blender, game-style prelight shading", font=font(17), fill=DIM, anchor="ra")
        for col, state in enumerate(("original", "reworked")):
            for row, time in enumerate(("noon", "midnight")):
                x, y = col * (WIDTH + GAP), BAR + row * (h + GAP)
                canvas.paste(tiles[(state, time)], (x, y))
                label(draw, (x + 14, y + 12), f"{state} · {time}")
        canvas.save(out / f"{house}.png", optimize=True)
        print(f"wrote screenshots/houses/{house}.png")
    details = sorted(renders.glob("*-detail.png"), key=lambda p: ("sf", "ls", "lv").index(p.name[:2]) * 10 + int(p.name[7]))
    if details:
        cell = (WIDTH // 2, round(WIDTH // 2 * 0.633))
        sheet = Image.new("RGB", (4 * cell[0] + 3 * GAP, BAR + 3 * cell[1] + 2 * GAP), BG)
        draw = ImageDraw.Draw(sheet, "RGBA")
        draw.text((14, 9), "window detail, reworked, noon", font=font(22, bold=True), fill=FG)
        for k, path in enumerate(details):
            x, y = (k % 4) * (cell[0] + GAP), BAR + (k // 4) * (cell[1] + GAP)
            sheet.paste(Image.open(path).convert("RGB").resize(cell, Image.LANCZOS), (x, y))
            label(draw, (x + 10, y + 8), path.name.split("-")[0])
        sheet.save(out / "details.png", optimize=True)
        print("wrote screenshots/houses/details.png")


if __name__ == "__main__":
    main()
