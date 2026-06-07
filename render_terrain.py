#!/usr/bin/env python3
"""Detailed terrain-only renderer for CityBench terrain JSON files.

This is not Google Maps data. It is a deterministic, map-like visualization of
the generated terrain layers: land cover, elevation shading, water edges,
contours, and scenario events.

    python render_terrain.py terrain_lake_core.json terrain_lake_core_detailed.png
"""

import json
import math
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont


CELL_M = 500

COLORS = {
    ".": (219, 214, 190),
    "T": (93, 133, 78),
    "F": (211, 194, 105),
    "w": (107, 161, 139),
    "^": (178, 172, 161),
    "~": (93, 157, 199),
}

EVENT_VIS = {
    "mineral_deposit": ("M", "opportunity"),
    "deep_harbor": ("H", "opportunity"),
    "oil_field": ("O", "mixed"),
    "fault_line": ("!", "hazard"),
    "floodplain": ("F", "mixed"),
    "heritage_site": ("G", "mixed"),
    "natural_reserve": ("N", "mixed"),
    "landslide_zone": ("L", "hazard"),
    "typhoon_corridor": ("T", "hazard"),
    "wind_corridor": ("W", "opportunity"),
    "aquifer_recharge": ("A", "mixed"),
    "scenic_viewpoint": ("V", "opportunity"),
    "geothermal_spring": ("S", "opportunity"),
    "fertile_soil": ("Y", "mixed"),
    "subsidence_zone": ("D", "hazard"),
    "bridge_chokepoint": ("B", "opportunity"),
}

RING = {
    "opportunity": (47, 151, 78),
    "hazard": (210, 64, 64),
    "mixed": (214, 150, 38),
}


def font(size, bold=False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/malgunbd.ttf" if bold else "C:/Windows/Fonts/malgun.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass
    return ImageFont.load_default()


def stable_seed(t):
    text = f"{t.get('terrain_key', '')}:{t.get('name', '')}:{t.get('objective', '')}"
    acc = 2166136261
    for ch in text:
        acc ^= ord(ch)
        acc = (acc * 16777619) & 0xFFFFFFFF
    return acc


def low_noise(rng, h, w, block):
    gh = max(2, math.ceil(h / block) + 2)
    gw = max(2, math.ceil(w / block) + 2)
    coarse = (rng.random((gh, gw)) * 255).astype(np.uint8)
    img = Image.fromarray(coarse, "L").resize((w, h), Image.Resampling.BICUBIC)
    return np.asarray(img, dtype=float) / 255.0


def hillshade(elev):
    gy, gx = np.gradient(elev.astype(float))
    light = -0.85 * gx - 0.55 * gy
    light = (light - light.min()) / (light.max() - light.min() + 1e-9)
    return 0.72 + light * 0.45


def terrain_arrays(t, scale):
    rows = np.array([list(r) for r in t["rows"]])
    h, w = rows.shape
    elev = np.array(t.get("elevation_m", []), dtype=float)
    if elev.shape != rows.shape:
        elev = np.zeros_like(rows, dtype=float)

    rows_hi = np.repeat(np.repeat(rows, scale, axis=0), scale, axis=1)
    elev_hi = np.repeat(np.repeat(elev, scale, axis=0), scale, axis=1)
    shade = np.repeat(np.repeat(hillshade(elev), scale, axis=0), scale, axis=1)

    rgb = np.zeros((h * scale, w * scale, 3), dtype=float)
    for key, color in COLORS.items():
        rgb[rows_hi == key] = color

    rng = np.random.default_rng(stable_seed(t))
    fine = low_noise(rng, h * scale, w * scale, max(12, scale * 3)) - 0.5
    broad = low_noise(rng, h * scale, w * scale, max(40, scale * 10)) - 0.5

    land = rows_hi != "~"
    rgb[land] *= shade[land, None]
    rgb[land] += fine[land, None] * 18 + broad[land, None] * 22

    forest = rows_hi == "T"
    rgb[forest] += fine[forest, None] * np.array([8, 18, 6])
    rgb[forest & (fine > 0.16)] *= np.array([0.82, 0.95, 0.82])

    farmland = rows_hi == "F"
    rgb[farmland] += broad[farmland, None] * np.array([28, 22, 8])

    wetland = rows_hi == "w"
    rgb[wetland] += fine[wetland, None] * np.array([4, 18, 22])
    rgb[wetland & (fine > 0.18)] = rgb[wetland & (fine > 0.18)] * 0.62 + np.array([80, 140, 170]) * 0.38

    water = rows_hi == "~"
    water_light = low_noise(rng, h * scale, w * scale, max(28, scale * 7))
    rgb[water] = np.array([83, 153, 202]) + (water_light[water, None] - 0.5) * np.array([18, 24, 30])

    steep = rows_hi == "^"
    rgb[steep] *= 0.92
    rgb[steep] += broad[steep, None] * np.array([18, 16, 14])

    return np.clip(rgb, 0, 255).astype(np.uint8), rows, elev, elev_hi


def draw_cell_edges(draw, rows, scale):
    h, w = rows.shape
    shore = (221, 236, 229, 170)
    wet_edge = (70, 124, 114, 90)
    field_edge = (122, 111, 65, 75)
    contour_edge = (118, 98, 70, 70)

    for y in range(h):
        for x in range(w):
            ch = rows[y, x]
            x0, y0 = x * scale, y * scale
            x1, y1 = x0 + scale, y0 + scale
            if ch == "F":
                if (x + y) % 3 == 0:
                    draw.line((x0, y0 + scale // 2, x1, y0 + scale // 2), fill=field_edge, width=1)
                if (x * 7 + y) % 5 == 0:
                    draw.line((x0 + scale // 2, y0, x0 + scale // 2, y1), fill=field_edge, width=1)
            for dx, dy, seg in (
                (1, 0, (x1, y0, x1, y1)),
                (-1, 0, (x0, y0, x0, y1)),
                (0, 1, (x0, y1, x1, y1)),
                (0, -1, (x0, y0, x1, y0)),
            ):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < w and 0 <= ny < h):
                    continue
                nb = rows[ny, nx]
                if ch == "~" and nb != "~":
                    draw.line(seg, fill=shore, width=2)
                elif ch == "w" and nb not in ("w", "~"):
                    draw.line(seg, fill=wet_edge, width=1)
                elif ch == "^" and nb not in ("^", "~"):
                    draw.line(seg, fill=contour_edge, width=1)


def draw_contours(draw, rows, elev, scale):
    valid = rows != "~"
    if not np.any(valid):
        return
    elev_min = float(elev[valid].min())
    elev_max = float(elev[valid].max())
    interval = 50 if elev_max - elev_min < 500 else 100
    contour = np.floor(elev / interval)
    h, w = rows.shape
    color = (92, 74, 46, 72)

    for y in range(h - 1):
        for x in range(w - 1):
            if rows[y, x] == "~":
                continue
            x0, y0 = x * scale, y * scale
            if rows[y, x + 1] != "~" and contour[y, x] != contour[y, x + 1]:
                draw.line((x0 + scale, y0, x0 + scale, y0 + scale), fill=color, width=1)
            if rows[y + 1, x] != "~" and contour[y, x] != contour[y + 1, x]:
                draw.line((x0, y0 + scale, x0 + scale, y0 + scale), fill=color, width=1)


def draw_events(draw, t, scale):
    cell = t.get("cell_size_m", CELL_M)
    badge_font = font(max(11, int(scale * 1.7)), bold=True)
    label_font = font(max(10, int(scale * 1.25)), bold=True)
    for event in t.get("events", []):
        letter, klass = EVENT_VIS.get(
            event.get("type"),
            (event.get("type", "?")[:1].upper(), event.get("class", "mixed")),
        )
        klass = event.get("class", klass)
        color = RING.get(klass, RING["mixed"])
        x = event["x"] / cell * scale
        y = event["y"] / cell * scale
        radius = event["radius"] / cell * scale
        rgba = (*color, 185)
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=rgba, width=max(2, scale // 3))
        r = max(9, int(scale * 1.4))
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, 230), outline=(*color, 255), width=2)
        draw.text((x, y), letter, anchor="mm", fill=(*color, 255), font=badge_font)
        name = event.get("name") or event.get("type", "")
        if scale >= 6 and name:
            draw.text((x + r + 4, y), name[:24], anchor="lm", fill=(35, 38, 34, 230), font=label_font)


def draw_overlays(img, t, rows, elev, scale):
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw_cell_edges(draw, rows, scale)
    draw_contours(draw, rows, elev, scale)
    draw_events(draw, t, scale)

    title_font = font(max(17, int(scale * 2.2)), bold=True)
    small_font = font(max(11, int(scale * 1.35)))
    title = f"{t.get('name', 'Terrain')} / {t.get('objective', '')}"
    climate = t.get("climate", {})
    sub = f"{climate.get('profile', '')}  rain {climate.get('rainfall_mm', '?')}mm  wind {climate.get('wind_index', '?')}"
    pad = max(10, scale * 2)
    box_w = max(360, int(scale * 55))
    box_h = max(70, int(scale * 10))
    draw.rounded_rectangle((pad, pad, pad + box_w, pad + box_h), radius=8,
                           fill=(255, 255, 255, 205), outline=(255, 255, 255, 235), width=1)
    draw.text((pad + 12, pad + 10), title, fill=(34, 37, 33, 240), font=title_font)
    draw.text((pad + 12, pad + 40), sub, fill=(60, 65, 60, 225), font=small_font)

    bar_km = 10
    bar_px = int((bar_km * 1000 / t.get("cell_size_m", CELL_M)) * scale)
    x0 = img.size[0] - pad - bar_px - 10
    y0 = img.size[1] - pad - 18
    draw.line((x0, y0, x0 + bar_px, y0), fill=(35, 35, 35, 230), width=4)
    draw.line((x0, y0 - 5, x0, y0 + 5), fill=(35, 35, 35, 230), width=2)
    draw.line((x0 + bar_px, y0 - 5, x0 + bar_px, y0 + 5), fill=(35, 35, 35, 230), width=2)
    draw.text((x0 + bar_px / 2, y0 - 9), f"{bar_km} km", anchor="mb",
              fill=(35, 35, 35, 230), font=small_font)

    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def render_image(t, scale=8):
    rgb, rows, elev, elev_hi = terrain_arrays(t, scale)
    img = Image.fromarray(rgb, "RGB")
    return draw_overlays(img, t, rows, elev, scale)


def render_file(terrain_path, out_path, scale=8):
    with open(terrain_path, encoding="utf-8") as f:
        terrain = json.load(f)
    img = render_image(terrain, scale=scale)
    img.save(out_path)
    return out_path


def main():
    if len(sys.argv) < 3:
        print("usage: python render_terrain.py terrain.json out.png [scale]")
        sys.exit(1)
    scale = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    print("rendered:", render_file(sys.argv[1], sys.argv[2], scale=scale))


if __name__ == "__main__":
    main()
