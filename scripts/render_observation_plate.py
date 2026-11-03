"""Render a travel observation plate from real photos and a JSON manifest."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

WIDTH, MARGIN, GAP = 1440, 42, 12
LAYOUTS = {
    2: [(0, 0, 2, 2), (2, 0, 1, 2)],
    3: [(0, 0, 3, 2), (0, 2, 2, 1), (2, 2, 1, 1)],
    4: [(0, 0, 2, 2), (2, 0, 1, 1), (2, 1, 1, 1), (0, 2, 3, 1)],
    5: [(0, 0, 2, 2), (2, 0, 1, 1), (2, 1, 1, 1), (0, 2, 1, 1), (1, 2, 2, 1)],
    6: [(0, 0, 2, 2), (2, 0, 1, 1), (2, 1, 1, 1), (0, 2, 1, 1), (1, 2, 1, 1), (2, 2, 1, 1)],
}


def wrap(draw, text, font, width):
    line = ""
    for char in text:
        if line and draw.textlength(line + char, font=font) > width:
            yield line
            line = ""
        line += char
    if line:
        yield line


def render(manifest, output, font_path):
    data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    panels = data["panels"]
    if len(panels) not in LAYOUTS:
        raise ValueError("Provide 2 to 6 panels.")
    layout = LAYOUTS[len(panels)]
    row = 355
    column = (WIDTH - 2 * MARGIN - 2 * GAP) // 3
    grid_height = max(y + h for _, y, _, h in layout) * (row + GAP) - GAP
    paper = "#f8f7f2"
    ink = "#222822"
    title_font = ImageFont.truetype(font_path, 53)
    label_font = ImageFont.truetype(font_path, 31)
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    title = list(wrap(measure, data["title"], title_font, WIDTH - 2 * MARGIN))
    caption = "   ".join(f"({chr(97 + i)}) {p['caption']}" for i, p in enumerate(panels))
    lines = list(wrap(measure, caption, label_font, WIDTH - 2 * MARGIN))
    top = MARGIN + 65 * len(title) + 22
    footer = top + grid_height + 28
    canvas = Image.new("RGB", (WIDTH, footer + 46 * len(lines) + MARGIN), paper)
    draw = ImageDraw.Draw(canvas)
    for i, line in enumerate(title):
        draw.text((MARGIN, MARGIN + 65 * i), line, font=title_font, fill=ink, anchor="lt")
    for index, (panel, (x, y, w, h)) in enumerate(zip(panels, layout)):
        with Image.open(manifest.parent / panel["file"]) as original:
            photo = ImageOps.exif_transpose(original).convert("RGB")
        if "crop" in panel:
            left, upper, right, lower = panel["crop"]
            if not (0 <= left < right <= 1 and 0 <= upper < lower <= 1):
                raise ValueError("crop must be a normalized [left, top, right, bottom] box.")
            photo = photo.crop((left * photo.width, upper * photo.height,
                                right * photo.width, lower * photo.height))
        size = (w * (column + GAP) - GAP, h * (row + GAP) - GAP)
        if panel.get("contain"):
            tile = Image.new("RGB", size, "#eae8df")
            resized = ImageOps.contain(photo, size, Image.Resampling.LANCZOS)
            tile.paste(resized, ((size[0] - resized.width) // 2, (size[1] - resized.height) // 2))
        else:
            tile = ImageOps.fit(photo, size, Image.Resampling.LANCZOS,
                                centering=tuple(panel.get("focus", [0.5, 0.5])))
        px = MARGIN + x * (column + GAP)
        py = top + y * (row + GAP)
        canvas.paste(tile, (px, py))
        tag = f"({chr(97 + index)})"
        draw.rectangle((px, py, px + int(draw.textlength(tag, font=label_font)) + 22, py + 49), fill=paper)
        draw.text((px + 11, py + 9), tag, font=label_font, fill=ink, anchor="lt")
    for i, line in enumerate(lines):
        draw.text((MARGIN, footer + 46 * i), line, font=label_font, fill=ink, anchor="lt")
    canvas.save(output, format="PNG")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--font", required=True, help="Path to a font that supports the caption language")
    args = parser.parse_args()
    render(args.manifest, args.output, args.font)

