#!/usr/bin/env python3
"""Generate a five-terrain montage for quick visual QA."""

import sys

from PIL import Image, ImageDraw

import render_terrain
import terrain_gen


TERRAINS = [
    ("lake_core", "Financial Capital", 3),
    ("twin_coast", "Logistics Hub", 3),
    ("mountain_gate", "Innovation City", 3),
    ("great_delta", "Logistics Hub", 3),
    ("central_plain", "Eco Metropolis", 3),
]


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "terrain_preview_v04.png"
    thumbs = []
    for ttype, objective, seed in TERRAINS:
        terrain = terrain_gen.build(ttype, objective, seed)
        img = render_terrain.render_image(terrain, scale=4)
        img = img.resize((560, 420), Image.Resampling.LANCZOS)
        thumbs.append((terrain["name"], img))

    canvas = Image.new("RGB", (1680, 900), "#f4f2ea")
    draw = ImageDraw.Draw(canvas)
    positions = [(0, 0), (560, 0), (1120, 0), (280, 450), (840, 450)]
    for (title, img), (x, y) in zip(thumbs, positions):
        canvas.paste(img, (x, y))
        draw.rectangle((x, y, x + 559, y + 419), outline="#ffffff", width=2)

    canvas.save(out)
    print("rendered:", out)


if __name__ == "__main__":
    main()
