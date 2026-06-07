#!/usr/bin/env python3
"""
CityBench terrain generator v0.4.

Procedural regional terrain with elevation, slope, water, land cover, climate
metadata, and static coordinate events. The submission/scoring surface is still
the compact row raster, but generated scenarios now carry richer layers for
rendering and future UI work.

    python terrain_gen.py <type> <objective> [seed] [out.json]

type: lake_core | twin_coast | mountain_gate | great_delta | central_plain

Row legend:
  . open urbanizable land
  T forest / woodland
  F farmland / cultivated plain
  w wetland / soft flood-prone land
  ^ steep slope / cliff
  ~ open water
"""

import json
import sys

import numpy as np

try:
    from scipy.ndimage import zoom, gaussian_filter
except ImportError:
    def zoom(arr, factors, order=3):
        out_h = max(1, int(round(arr.shape[0] * factors[0])))
        out_w = max(1, int(round(arr.shape[1] * factors[1])))
        ys = np.linspace(0, arr.shape[0] - 1, out_h)
        xs = np.linspace(0, arr.shape[1] - 1, out_w)
        y0 = np.floor(ys).astype(int)
        x0 = np.floor(xs).astype(int)
        y1 = np.clip(y0 + 1, 0, arr.shape[0] - 1)
        x1 = np.clip(x0 + 1, 0, arr.shape[1] - 1)
        wy = (ys - y0)[:, None]
        wx = (xs - x0)[None, :]
        top = arr[y0[:, None], x0[None, :]] * (1 - wx) + arr[y0[:, None], x1[None, :]] * wx
        bot = arr[y1[:, None], x0[None, :]] * (1 - wx) + arr[y1[:, None], x1[None, :]] * wx
        return top * (1 - wy) + bot * wy

    def gaussian_filter(arr, sigma):
        if sigma <= 0:
            return arr
        radius = max(1, int(np.ceil(sigma * 3)))
        x = np.arange(-radius, radius + 1)
        kernel = np.exp(-(x * x) / (2 * sigma * sigma))
        kernel /= kernel.sum()

        padded = np.pad(arr.astype(float), ((0, 0), (radius, radius)), mode="edge")
        tmp = np.empty_like(arr, dtype=float)
        for y in range(arr.shape[0]):
            tmp[y] = np.convolve(padded[y], kernel, mode="valid")

        padded = np.pad(tmp, ((radius, radius), (0, 0)), mode="edge")
        out = np.empty_like(tmp, dtype=float)
        for x_i in range(arr.shape[1]):
            out[:, x_i] = np.convolve(padded[:, x_i], kernel, mode="valid")
        return out


CELL = 500
W, H = 200, 150  # 100km x 75km

DIFFICULTY = {
    "lake_core": 1.05,
    "twin_coast": 1.10,
    "mountain_gate": 1.35,
    "great_delta": 1.30,
    "central_plain": 0.95,
}

TYPE_NAME = {
    "lake_core": "Lake Core",
    "twin_coast": "Coastal Bay",
    "mountain_gate": "Mountain Basin",
    "great_delta": "River Delta",
    "central_plain": "Great Plain",
}

SEA = {
    "lake_core": 0.31,
    "twin_coast": 0.29,
    "mountain_gate": -1.0,
    "great_delta": 0.24,
    "central_plain": -1.0,
}

ELEV_RANGE_M = {
    "lake_core": (40, 720),
    "twin_coast": (0, 620),
    "mountain_gate": (260, 2450),
    "great_delta": (0, 190),
    "central_plain": (60, 430),
}

LANDCOVER_LEGEND = {
    ".": "open land",
    "T": "forest",
    "F": "farmland",
    "w": "wetland",
    "^": "steep slope",
    "~": "water",
}

EVENT_META = {
    "mineral_deposit": ("opportunity", "Resource discovery"),
    "deep_harbor": ("opportunity", "Natural deep harbor"),
    "oil_field": ("mixed", "Oil field"),
    "fault_line": ("hazard", "Active fault line"),
    "floodplain": ("mixed", "Floodplain"),
    "heritage_site": ("mixed", "Heritage site"),
    "natural_reserve": ("mixed", "Natural reserve"),
    "landslide_zone": ("hazard", "Landslide risk zone"),
    "typhoon_corridor": ("hazard", "Typhoon exposure corridor"),
    "wind_corridor": ("opportunity", "High wind corridor"),
    "aquifer_recharge": ("mixed", "Aquifer recharge zone"),
    "scenic_viewpoint": ("opportunity", "Scenic viewpoint"),
    "geothermal_spring": ("opportunity", "Geothermal spring"),
    "fertile_soil": ("mixed", "Prime farmland"),
    "subsidence_zone": ("hazard", "Soft-ground subsidence zone"),
}


def normalize(arr):
    return (arr - arr.min()) / (arr.max() - arr.min() + 1e-9)


def fbm(rng, octaves=6, persistence=0.55):
    out = np.zeros((H, W))
    amp = 1.0
    norm = 0.0
    for o in range(octaves):
        c = 2 ** (o + 1)
        coarse = rng.random((c + 1, c + 1))
        big = zoom(coarse, (H / (c + 1), W / (c + 1)), order=3)[:H, :W]
        out += amp * big
        norm += amp
        amp *= persistence
    return normalize(out / norm)


def grid_xy():
    ys, xs = np.mgrid[0:H, 0:W]
    return xs.astype(float), ys.astype(float), xs / (W - 1), ys / (H - 1)


def shape(ttype, base, rng):
    xs, ys, nx, ny = grid_xy()
    ridges = fbm(rng, octaves=4, persistence=0.45)

    if ttype == "lake_core":
        basin_a = np.exp(-(((nx - 0.47) ** 2) / 0.035 + ((ny - 0.45) ** 2) / 0.055))
        basin_b = np.exp(-(((nx - 0.36) ** 2) / 0.020 + ((ny - 0.60) ** 2) / 0.025))
        eastern_upland = 0.24 * nx + 0.08 * np.sin(ny * np.pi * 3)
        return normalize(base * 0.55 + ridges * 0.18 + eastern_upland - basin_a * 0.95 - basin_b * 0.45)

    if ttype == "twin_coast":
        coastal_low = np.minimum(nx, 1 - nx)
        center_rise = np.clip((coastal_low - 0.10) / 0.42, 0, 1)
        estuary = np.exp(-(((nx - 0.50) ** 2) / 0.020 + ((ny - 0.62) ** 2) / 0.030))
        return normalize(base * 0.35 + ridges * 0.16 + center_rise * 0.78 - estuary * 0.42)

    if ttype == "mountain_gate":
        north = np.exp(-((ny - 0.16) ** 2) / 0.012)
        south = np.exp(-((ny - 0.85) ** 2) / 0.015)
        pass_gap = np.exp(-(((nx - 0.52) ** 2) / 0.070 + ((ny - 0.51) ** 2) / 0.035))
        side_ridges = 0.25 * np.abs(nx - 0.5)
        return normalize(base * 0.38 + ridges * 0.30 + north * 0.85 + south * 0.78 + side_ridges - pass_gap * 0.55)

    if ttype == "great_delta":
        inland_tilt = 1.0 - ny
        delta_fan = np.exp(-(((nx - 0.50) ** 2) / 0.12 + ((ny - 0.82) ** 2) / 0.05))
        return normalize(base * 0.34 + ridges * 0.10 + inland_tilt * 0.70 - delta_fan * 0.28)

    if ttype == "central_plain":
        shallow_valley = np.exp(-(((nx - 0.42) ** 2) / 0.10 + ((ny - 0.56) ** 2) / 0.16))
        low_ridges = 0.08 * np.sin(nx * np.pi * 4) + 0.05 * np.cos(ny * np.pi * 3)
        return normalize(base * 0.28 + ridges * 0.14 + low_ridges - shallow_valley * 0.18 + 0.40)

    return base


def flow_accumulation(elev):
    acc = np.ones((H, W))
    order = np.argsort(elev, axis=None)[::-1]
    nb = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    for idx in order:
        y, x = divmod(int(idx), W)
        best = None
        best_z = elev[y, x]
        for dy, dx in nb:
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W and elev[ny, nx] < best_z:
                best_z = elev[ny, nx]
                best = (ny, nx)
        if best:
            acc[best] += acc[y, x]
    return acc


def river_mask(ttype, elev, water):
    if ttype == "twin_coast":
        q = 0.982
    elif ttype == "great_delta":
        q = 0.945
    elif ttype == "lake_core":
        q = 0.988
    elif ttype == "mountain_gate":
        q = 0.984
    else:
        q = 0.986
    acc = flow_accumulation(elev)
    river = (acc > np.quantile(acc, q)) & (~water)
    river = gaussian_filter(river.astype(float), 0.55) > 0.24
    return river


def build_grid(ttype, rng):
    base = fbm(rng)
    elev = shape(ttype, base, rng)
    water = elev < SEA[ttype]
    river = river_mask(ttype, elev, water)
    water = water | river

    smooth_elev = gaussian_filter(elev, 1.0)
    gy, gx = np.gradient(smooth_elev)
    slope = normalize(np.hypot(gx, gy))
    steep_q = 0.89 if ttype == "mountain_gate" else 0.973
    steep = (slope > np.quantile(slope, steep_q)) & (~water)

    water_influence = normalize(gaussian_filter(water.astype(float), 5.5))
    moist_noise = fbm(np.random.default_rng(int(rng.integers(1, 1_000_000_000))), octaves=5)
    moisture = normalize(0.52 * moist_noise + 0.35 * water_influence + 0.18 * (1 - elev))
    cover_noise = fbm(np.random.default_rng(int(rng.integers(1, 1_000_000_000))), octaves=5)

    lowland = elev < np.quantile(elev[~water], 0.42)
    wetland_bias = {
        "great_delta": 0.18,
        "lake_core": 0.26,
        "twin_coast": 0.23,
        "central_plain": 0.30,
        "mountain_gate": 0.42,
    }[ttype]
    wetland = (water_influence > wetland_bias) & lowland & (moisture > 0.42) & (~water) & (~steep)

    forest_q = {
        "mountain_gate": 0.48,
        "lake_core": 0.56,
        "twin_coast": 0.60,
        "great_delta": 0.64,
        "central_plain": 0.68,
    }[ttype]
    forest = (moisture + cover_noise * 0.45 > forest_q) & (~water) & (~steep) & (~wetland)

    slope_plain = slope < np.quantile(slope[~water], 0.48)
    farm_bias = {
        "central_plain": 0.62,
        "great_delta": 0.52,
        "twin_coast": 0.38,
        "lake_core": 0.35,
        "mountain_gate": 0.18,
    }[ttype]
    farmland = (
        slope_plain
        & (moisture > 0.28)
        & (moisture < 0.76)
        & (cover_noise < farm_bias)
        & (~water)
        & (~steep)
        & (~wetland)
        & (~forest)
    )

    g = np.full((H, W), ".", dtype="<U1")
    g[farmland] = "F"
    g[forest] = "T"
    g[wetland] = "w"
    g[steep] = "^"
    g[water] = "~"

    lo, hi = ELEV_RANGE_M[ttype]
    elev_m = np.rint(lo + elev * (hi - lo)).astype(int)
    return {
        "rows": g,
        "elev": elev,
        "elev_m": elev_m,
        "slope": slope,
        "moisture": moisture,
        "water": water,
        "steep": steep,
        "wetland": wetland,
        "forest": forest,
        "farmland": farmland,
        "water_influence": water_influence,
    }


def place_events(ttype, layers, rng):
    g = layers["rows"]
    elev = layers["elev"]
    slope = layers["slope"]
    water = layers["water"]
    wetland = layers["wetland"]
    forest = layers["forest"]
    farmland = layers["farmland"]
    water_influence = layers["water_influence"]
    land = (g != "~") & (g != "^")
    events = []

    def choose(mask, score=None):
        ys, xs = np.where(mask)
        if len(xs) == 0:
            return None
        if score is not None:
            vals = score[ys, xs]
            cutoff = np.quantile(vals, 0.86) if len(vals) > 12 else vals.min()
            keep = vals >= cutoff
            xs, ys = xs[keep], ys[keep]
        i = int(rng.integers(0, len(xs)))
        return int(xs[i]), int(ys[i])

    def coast_cell(score=None):
        cand = np.zeros_like(land, dtype=bool)
        ys, xs = np.where(land)
        for x, y in zip(xs, ys):
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < W and 0 <= ny < H and water[ny, nx]:
                    cand[y, x] = True
                    break
        return choose(cand, score)

    def add(etype, cell, radius_km, **extra):
        if not cell:
            return
        klass, default_name = EVENT_META[etype]
        events.append({
            "type": etype,
            "class": extra.pop("class", klass),
            "name": extra.pop("name", default_name),
            "x": (cell[0] + 0.5) * CELL,
            "y": (cell[1] + 0.5) * CELL,
            "radius": radius_km * 1000,
            **extra,
        })

    high_ground = land & (elev > np.quantile(elev[land], 0.70))
    low_wet = land & ((wetland) | (water_influence > 0.36))
    steep_land = (g == "^") | (land & (slope > np.quantile(slope[land], 0.82)))
    open_plain = land & (g != "T") & (slope < np.quantile(slope[land], 0.45))

    if ttype == "lake_core":
        add("scenic_viewpoint", coast_cell(elev + water_influence), 4, name="Lakefront scenic rim")
        add("aquifer_recharge", choose(low_wet, water_influence), 6, name="Lake aquifer recharge zone")
        add("mineral_deposit", choose(high_ground, elev), 4, resource="lithium")
        add("fault_line", choose(steep_land, slope), 5)

    elif ttype == "twin_coast":
        add("deep_harbor", coast_cell(water_influence), 4, name="Deep-water harbor site")
        add("typhoon_corridor", coast_cell(water_influence), 7)
        add("wind_corridor", coast_cell(water_influence + slope * 0.2), 5, name="Offshore wind landing zone")
        add("oil_field", choose(open_plain, water_influence), 5, resource="oil")

    elif ttype == "mountain_gate":
        add("mineral_deposit", choose(steep_land, elev + slope), 4, resource="iron")
        add("landslide_zone", choose(steep_land, slope), 5)
        add("scenic_viewpoint", choose(high_ground & (forest | land), elev), 4, name="Alpine tourism ridge")
        add("geothermal_spring", choose(land & (water_influence > 0.10), water_influence + elev * 0.2), 4)

    elif ttype == "great_delta":
        add("floodplain", choose(low_wet, water_influence), 7)
        add("deep_harbor", coast_cell(water_influence), 4)
        add("aquifer_recharge", choose(wetland | low_wet, water_influence), 6)
        add("subsidence_zone", choose(low_wet, water_influence), 6)

    elif ttype == "central_plain":
        add("fertile_soil", choose(farmland | open_plain, 1 - slope), 6)
        add("wind_corridor", choose(open_plain, 1 - slope), 6)
        add("floodplain", choose(low_wet, water_influence), 6)
        add("mineral_deposit", choose(high_ground | open_plain, elev), 4, resource="iron")

    return events


def layer_stats(rows, layers):
    stats = {key: int(np.sum(rows == key)) for key in LANDCOVER_LEGEND}
    land = rows != "~"
    return {
        "cells": stats,
        "elevation_m": {
            "min": int(layers["elev_m"][land].min()),
            "mean": int(np.rint(layers["elev_m"][land].mean())),
            "max": int(layers["elev_m"][land].max()),
        },
        "mean_slope": round(float(layers["slope"][land].mean()), 3),
        "mean_moisture": round(float(layers["moisture"][land].mean()), 3),
    }


def climate_profile(ttype, layers):
    base = {
        "lake_core": (920, 13.5, "temperate lake basin"),
        "twin_coast": (1180, 15.0, "humid coastal"),
        "mountain_gate": (760, 8.5, "cool mountain basin"),
        "great_delta": (1320, 16.5, "humid delta"),
        "central_plain": (680, 14.0, "continental plain"),
    }[ttype]
    rain, temp, label = base
    wet_bonus = int(layers["water_influence"].mean() * 180)
    return {
        "profile": label,
        "rainfall_mm": rain + wet_bonus,
        "avg_temp_c": temp,
        "wind_index": round({
            "lake_core": 0.45,
            "twin_coast": 0.78,
            "mountain_gate": 0.62,
            "great_delta": 0.55,
            "central_plain": 0.72,
        }[ttype], 2),
    }


def build(ttype, objective, seed=0):
    if ttype not in TYPE_NAME:
        raise SystemExit(f"unknown terrain type: {ttype}")

    rng = np.random.default_rng(seed)
    layers = build_grid(ttype, rng)
    rows_arr = layers["rows"]
    rows = ["".join(r) for r in rows_arr]
    events = place_events(ttype, layers, rng)

    buildable = int(np.sum((rows_arr != "~") & (rows_arr != "^")))
    bkm2 = buildable * (CELL / 1000) ** 2
    res_t = int(bkm2 * 500)
    job_t = int(bkm2 * 250)

    return {
        "name": f"{TYPE_NAME[ttype]} #{seed}",
        "terrain_type": TYPE_NAME[ttype],
        "terrain_key": ttype,
        "objective": objective,
        "difficulty": DIFFICULTY[ttype],
        "cell_size_m": CELL,
        "width": W,
        "height": H,
        "budget": int(res_t * 1.6),
        "targets": {"residents": res_t, "jobs": job_t},
        "landcover_legend": LANDCOVER_LEGEND,
        "climate": climate_profile(ttype, layers),
        "layer_stats": layer_stats(rows_arr, layers),
        "elevation_m": layers["elev_m"].tolist(),
        "events": events,
        "rows": rows,
    }


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    ttype, obj = sys.argv[1], sys.argv[2]
    seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    out = sys.argv[4] if len(sys.argv) > 4 else f"terrain_{ttype}.json"
    terrain = build(ttype, obj, seed)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(terrain, f, ensure_ascii=False)
    cells = terrain["layer_stats"]["cells"]
    events = [f"{e['type']}:{e['class']}" for e in terrain["events"]]
    print(
        f"{out} build {cells['.'] + cells['T'] + cells['F'] + cells['w']}, "
        f"water {cells['~']}, steep {cells['^']}, "
        f"forest {cells['T']}, wetland {cells['w']}, farmland {cells['F']}, "
        f"events {events}"
    )


if __name__ == "__main__":
    main()
