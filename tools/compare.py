"""Build before/after comparison images from screenshots/before and screenshots/after.

usage: python tools/compare.py   (run from the repo root)

For every shot present in both sets, writes screenshots/compare/<shot>.png: a 2x2 grid with before on the left,
after on the right, noon on top and midnight below, plus a small caption bar.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
WIDTH = 760  # per tile
GAP = 6
BAR = 44
BG = (18, 18, 22)
FG = (235, 235, 240)
DIM = (150, 150, 160)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for name in ("segoeuib.ttf" if bold else "segoeui.ttf", "arialbd.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def tile(path: Path) -> Image.Image:
    img = Image.open(path).convert("RGB")
    return img.resize((WIDTH, round(img.height * WIDTH / img.width)), Image.LANCZOS)


def label(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str) -> None:
    f = font(20, bold=True)
    x, y = xy
    box = draw.textbbox((x, y), text, font=f)
    draw.rounded_rectangle((box[0] - 8, box[1] - 5, box[2] + 8, box[3] + 5), radius=6, fill=(0, 0, 0, 170))
    draw.text((x, y), text, font=f, fill=FG)


def main() -> None:
    before, after, out = ROOT / "screenshots" / "before", ROOT / "screenshots" / "after", ROOT / "screenshots" / "compare"
    out.mkdir(parents=True, exist_ok=True)
    shots = sorted({p.name.rsplit("-", 1)[0] for p in after.glob("*-noon.png")})
    for shot in shots:
        paths = {(s, t): d / f"{shot}-{t}.png" for s, d in (("before", before), ("after", after)) for t in ("noon", "midnight")}
        if not all(p.exists() for p in paths.values()):
            continue
        tiles = {k: tile(p) for k, p in paths.items()}
        h = tiles[("before", "noon")].height
        canvas = Image.new("RGB", (2 * WIDTH + GAP, BAR + 2 * h + GAP), BG)
        draw = ImageDraw.Draw(canvas, "RGBA")
        draw.text((14, 9), shot, font=font(22, bold=True), fill=FG)
        draw.text((2 * WIDTH + GAP - 14, 12), "Ariane viewport, weather 1", font=font(17), fill=DIM, anchor="ra")
        for col, s in enumerate(("before", "after")):
            for row, t in enumerate(("noon", "midnight")):
                x, y = col * (WIDTH + GAP), BAR + row * (h + GAP)
                canvas.paste(tiles[(s, t)], (x, y))
                label(draw, (x + 14, y + 12), f"{s} · {t}")
        canvas.save(out / f"{shot}.png", optimize=True)
        print(f"wrote screenshots/compare/{shot}.png")


if __name__ == "__main__":
    main()
