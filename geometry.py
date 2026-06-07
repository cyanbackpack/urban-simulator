#!/usr/bin/env python3
"""Small geometry helpers for CityBench vector submissions.

Coordinates are metres in the same top-left origin system as the terrain.
Raster functions return ``(x, y)`` cell coordinates clipped to the terrain.
"""

import math


def m_to_cell(x, y, cell_size_m):
    return int(x // cell_size_m), int(y // cell_size_m)


def polyline_length_km(path):
    total = 0.0
    for (x1, y1), (x2, y2) in zip(path, path[1:]):
        total += math.hypot(x2 - x1, y2 - y1)
    return total / 1000.0


def fill_polygon(poly, cell_size_m, width, height):
    if len(poly) < 3:
        return []

    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    min_x = max(0, int(math.floor(min(xs) / cell_size_m)))
    max_x = min(width - 1, int(math.floor(max(xs) / cell_size_m)))
    min_y = max(0, int(math.floor(min(ys) / cell_size_m)))
    max_y = min(height - 1, int(math.floor(max(ys) / cell_size_m)))

    cells = []
    for cy in range(min_y, max_y + 1):
        py = (cy + 0.5) * cell_size_m
        for cx in range(min_x, max_x + 1):
            px = (cx + 0.5) * cell_size_m
            if _point_in_polygon(px, py, poly):
                cells.append((cx, cy))
    return cells


def raster_line(path, cell_size_m, width, height):
    if len(path) < 2:
        return []

    out = []
    seen = set()

    def add(cx, cy):
        if 0 <= cx < width and 0 <= cy < height and (cx, cy) not in seen:
            seen.add((cx, cy))
            out.append((cx, cy))

    prev = None
    for p1, p2 in zip(path, path[1:]):
        x1, y1 = p1
        x2, y2 = p2
        dist = math.hypot(x2 - x1, y2 - y1)
        steps = max(1, int(math.ceil(dist / (cell_size_m * 0.5))))
        for i in range(steps + 1):
            t = i / steps
            cx, cy = m_to_cell(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, cell_size_m)
            if prev is not None and prev != (cx, cy):
                px, py = prev
                if px != cx and py != cy:
                    add(cx, py)
            add(cx, cy)
            prev = (cx, cy)

    return out


def _point_in_polygon(x, y, poly):
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if _point_on_segment(x, y, x1, y1, x2, y2):
            return True
        crosses = (y1 > y) != (y2 > y)
        if crosses:
            x_at_y = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < x_at_y:
                inside = not inside
    return inside


def _point_on_segment(px, py, x1, y1, x2, y2):
    cross = (px - x1) * (y2 - y1) - (py - y1) * (x2 - x1)
    if abs(cross) > 1e-7:
        return False
    return (
        min(x1, x2) - 1e-7 <= px <= max(x1, x2) + 1e-7
        and min(y1, y2) - 1e-7 <= py <= max(y1, y2) + 1e-7
    )
