#!/usr/bin/env python3
"""Generate an optimised ("elite") exemplar submission for a terrain.

Where make_reference.py produces a deliberately mediocre baseline (the floor of
the benchmark), this produces a polished plan that an expert planner would be
happy with: footprints sized from the terrain's own population/jobs targets, a
compact transit-served core, a full ring of mobility hubs, generous green
structure, and facilities snapped onto the terrain's opportunity events. These
are the public model answers -- every case should reach at least A, and the
strongest should prove that S is achievable.

    python make_elite.py terrain.json submission_elite.json
"""

import json
import math
import sys

import numpy as np

import score_v2 as S
from make_reference import Planner, rect, build_transit, event_point


# zones whose footprint we size from targets
RES_DENSITY = S.ZONES["RES_HIGH"]["res"]      # residents / km2
JOB_DENSITY = S.ZONES["CBD"]["job"]           # jobs / km2


def _cells_for(amount, density, cell_km2):
    """How many cells of the given density to reach `amount`."""
    return max(1, int(math.ceil(amount / (density * cell_km2))))


def _block_dims(n_cells):
    """Pick a near-square half-width/half-height covering >= n_cells."""
    side = max(4, int(math.ceil(math.sqrt(n_cells))))
    hw = max(4, side // 2)
    hh = max(4, int(math.ceil(n_cells / (hw * 2) / 2)))
    return hw, hh


def _add(zones, planner, use, desired, hw, hh, prefer_open):
    return planner.add_zone(zones, use, desired, hw, hh, prefer_open=prefer_open)


# Events whose radius penalises any people/industry inside it: the city core
# should sit as far from these as the buildable land allows.
HAZARD_EVENTS = ("fault_line", "landslide_zone", "floodplain", "typhoon_corridor",
                 "subsidence_zone", "natural_reserve")


def choose_anchor(planner, terrain, radius=18):
    """Pick a city centre that is buildable, surrounded by buildable land
    (so the city can stay compact), and as far as possible from hazard events.
    Returns (cx, cy) in cells.
    """
    from make_reference import prefix, rect_sum
    cell = planner.cell
    h, w = planner.h, planner.w
    # "Clean" land = buildable AND not sensitive (forest/wetland). This matches
    # what the placer actually prefers, so the anchor lands on land the city
    # can really use instead of forest the placer will then avoid.
    clean = planner.buildable & ~planner.sensitive
    clean_pref = prefix(clean)
    hazards = [(e["x"] / cell, e["y"] / cell, e["radius"] / cell)
               for e in terrain.get("events", []) if e["type"] in HAZARD_EVENTS]

    best = None
    r = radius
    step = 2
    for cy in range(r, h - r, step):
        for cx in range(r, w - r, step):
            if not clean[cy, cx]:
                continue
            # clean-land density in the surrounding box (compactness headroom)
            x0, y0, x1, y1 = cx - r, cy - r, cx + r, cy + r
            open_frac = rect_sum(clean_pref, x0, y0, x1, y1) / ((2 * r) * (2 * r))
            if open_frac < 0.45:
                continue
            # distance to nearest hazard edge (cells); want it large
            haz = 1e9
            for hx, hy, hr in hazards:
                d = math.hypot(cx - hx, cy - hy) - hr
                haz = min(haz, d)
            if not hazards:
                haz = 30
            # prefer central anchors so the network/proximity stay strong
            centrality = 1 - (math.hypot(cx - w / 2, cy - h / 2) / math.hypot(w / 2, h / 2))
            score = open_frac * 20 + min(haz, 25) + centrality * 12
            if best is None or score > best[0]:
                best = (score, cx, cy)
    if best is None:
        return None
    return best[1], best[2]


def generate_elite_submission(terrain):
    planner = Planner(terrain)
    cell = planner.cell
    cell_km2 = (cell / 1000.0) ** 2
    objective = terrain.get("objective", "Financial Capital")
    tgt = terrain["targets"]

    # Anchor the city on a compact, buildable patch that is well clear of the
    # terrain's hazard events, then reserve the CBD core there.
    anchor = choose_anchor(planner, terrain)
    start = None
    if anchor:
        # prefer_open=False so the core stays at the hazard-safe anchor instead
        # of drifting to the most open (but possibly hazardous) patch.
        start = planner.find_rect(anchor, 6, 6, prefer_open=False)
    if not start:
        start = planner.find_rect((terrain["width"] // 2, int(terrain["height"] * 0.55)), 6, 6)
    if not start:
        start = (terrain["width"] // 2, terrain["height"] // 2)
    ax, ay = start

    # Confine the whole city to a box around the anchor by marking everything
    # outside it as occupied. This keeps wards compact (good sprawl/proximity)
    # and stops them scattering onto distant -- often hazardous -- patches of
    # buildable land on fragmented or heavily-forested terrain.
    res_cells_total = _cells_for(tgt["residents"] * 1.15, RES_DENSITY, cell_km2)
    box_r = max(22, int(math.sqrt(res_cells_total * 2.4 / math.pi) * 1.3))
    bx0, bx1 = max(0, ax - box_r), min(planner.w, ax + box_r + 1)
    by0, by1 = max(0, ay - box_r), min(planner.h, ay + box_r + 1)
    confine = np.ones_like(planner.occupied, dtype=bool)
    confine[by0:by1, bx0:bx1] = False
    planner.occupied |= confine

    zones = []
    zones.append({"use": "CBD", "polygon": rect(ax, ay, 6, 6, cell)})

    # --- jobs: keep ~1.0x the target so the jobs/residents ratio lands near
    #     the affordability sweet spot (0.45). One dominant CBD plus two smaller
    #     secondary centres, spaced far enough to read as distinct employment
    #     clusters, gives a polycentric structure (urban-form sub-score) and
    #     agglomeration without over-supplying jobs.
    _add(zones, planner, "CBD", (ax + 14, ay - 3), 4, 4, False)        # secondary centre
    _add(zones, planner, "COMMERCIAL", (ax - 13, ay + 3), 5, 4, False)  # third centre
    _add(zones, planner, "COMMERCIAL", (ax + 2, ay + 15), 4, 4, False)  # fourth centre

    # --- residents: size from the population target, kept in a tight cluster
    #     so the radius of gyration (sprawl control) stays low.
    res_cells = _cells_for(tgt["residents"] * 1.15, RES_DENSITY, cell_km2)
    ward_offsets = [(13, 5), (-13, 7), (5, 14), (-6, -13), (14, -10), (-14, -9)]
    per = res_cells / len(ward_offsets)
    hw, hh = _block_dims(per)
    for i, (dx, dy) in enumerate(ward_offsets):
        use = "RES_HIGH" if i < 4 else "RES_MED"
        _add(zones, planner, use, (ax + dx, ay + dy), hw, hh, True)

    # --- green: a fine mesh of pocket parks woven through and around the wards
    #     so almost every resident is within a short walk of one (this is the
    #     main lever on housing quality), plus large belts on the edge for
    #     eco-continuity and carbon. Parks sit both inside the ward ring and on
    #     a slightly larger ring so ward interiors and edges are both covered.
    park_offsets = [(0, 6), (0, -6), (6, 0), (-6, 0), (9, 9), (-9, 9),
                    (9, -9), (-9, -9), (0, 11), (0, -11), (11, 4), (-11, 4)]
    park_offsets += [(13, 0), (-13, 0), (0, 16), (0, -16), (16, 10),
                     (-16, 10), (16, -8), (-16, -8), (8, 16), (-8, 16)]
    for dx, dy in park_offsets:
        _add(zones, planner, "PARK", (ax + dx, ay + dy), 3, 3, True)
    _add(zones, planner, "GREENBELT", (ax - 24, ay), 8, 8, True)
    _add(zones, planner, "GREENBELT", (ax + 24, ay + 14), 7, 7, True)
    _add(zones, planner, "PUBLIC", (ax - 4, ay - 6), 3, 3, False)

    # Lift the confinement box: industry, facilities and hazard buffers may
    # (and often should) sit well outside the compact residential core.
    planner.occupied &= ~confine

    # --- hazard mitigation: drop a green buffer onto each hazard event so we
    #     neither build people/industry on it nor leave it bare. Several hazard
    #     events reward a green buffer and stop penalising once homes stay away.
    HAZARDS = ("fault_line", "landslide_zone", "floodplain", "typhoon_corridor",
               "subsidence_zone", "natural_reserve", "heritage_site")
    for ev in terrain.get("events", []):
        if ev["type"] in HAZARDS:
            hx, hy = planner.find_point((int(ev["x"] / cell), int(ev["y"] / cell)))
            _add(zones, planner, "GREENBELT", (hx, hy), 4, 4, True)

    # --- objective-specific structure, snapped onto opportunity events ------
    facilities = []

    def fac(ftype, pt):
        if pt:
            x, y = pt
            facilities.append({"type": ftype, "x": x, "y": y})

    def fac_at_event(ftype, etype, fallback):
        pt = event_point(terrain, etype)
        fac(ftype, pt if pt else planner.meters(planner.find_point(fallback)))

    # dirty/industrial structure is pushed into one outer sector, away from
    # homes and water, so it doesn't tax the environment/quality metrics.
    far = (min(planner.w - 8, ax + 34), min(planner.h - 8, ay + 26))

    if objective == "Financial Capital":
        _add(zones, planner, "COMMERCIAL", (ax + 6, ay + 6), 4, 3, False)
        fac("airport", planner.meters(planner.find_point((max(10, ax - 58), max(10, ay - 46)))))
    elif objective == "Logistics Hub":
        # industry snapped onto mineral/oil where present, else the far sector
        placed = False
        for et in ("mineral_deposit", "oil_field"):
            pt = event_point(terrain, et)
            if pt:
                mx, my = planner.find_point((int(pt[0] / cell), int(pt[1] / cell)))
                _add(zones, planner, "INDUSTRIAL", (mx, my), 6, 5, False)
                placed = True
        if not placed:
            _add(zones, planner, "INDUSTRIAL", (ax + 30, ay + 20), 6, 5, False)
        _add(zones, planner, "LOGISTICS", (ax + 36, ay + 22), 6, 5, False)
        fac_at_event("port", "deep_harbor", (min(planner.w - 8, ax + 40), ay + 14))
        fac("freight_terminal", planner.meters(planner.find_point(far)))
    elif objective == "Innovation City":
        _add(zones, planner, "UNIVERSITY", (ax - 11, ay - 11), 5, 5, False)
        _add(zones, planner, "MEDICAL", (ax + 9, ay - 11), 4, 4, False)
        fac_at_event("water_treatment", "aquifer_recharge", (ax - 4, ay + 14))
    elif objective == "Eco Metropolis":
        _add(zones, planner, "GREENBELT", (ax + 4, ay + 26), 8, 6, True)
        fac_at_event("power", "wind_corridor", far)
        fac_at_event("water_treatment", "aquifer_recharge", (ax - 4, ay + 14))
    elif objective == "Tourism Capital":
        _add(zones, planner, "PARK", (ax - 16, ay - 14), 6, 5, True)
        _add(zones, planner, "RES_LOW", (ax + 22, ay - 12), 7, 5, True)
        fac("airport", planner.meters(planner.find_point((max(10, ax - 58), max(10, ay - 46)))))
        fac_at_event("port", "deep_harbor", (min(planner.w - 8, ax + 38), ay + 12))

    # clean power, kept in the far sector if the objective didn't place one
    if not any(f["type"] == "power" for f in facilities):
        fac("power", planner.meters(planner.find_point(far)))

    # --- transit: dense core mesh + radial subways + a loop -----------------
    transit, stations, hubs = build_transit(terrain, (ax, ay), objective)
    # A fine arterial grid over the core lifts the transit-served share so most
    # residents sit within the 2-cell walk window of a corridor.
    lo_x, hi_x = max(1, ax - 20), min(planner.w - 1, ax + 20)
    lo_y, hi_y = max(1, ay - 18), min(planner.h - 1, ay + 18)
    for x in range(lo_x, hi_x + 1, 4):
        transit.append({"type": "arterial", "path": [[x * cell, lo_y * cell], [x * cell, hi_y * cell]]})
    for y in range(lo_y, hi_y + 1, 4):
        transit.append({"type": "arterial", "path": [[lo_x * cell, y * cell], [hi_x * cell, y * cell]]})
    # subway loop around the core
    transit.append({"type": "subway", "path": [
        [(ax - 16) * cell, (ay - 14) * cell], [(ax + 16) * cell, (ay - 14) * cell],
        [(ax + 16) * cell, (ay + 14) * cell], [(ax - 16) * cell, (ay + 14) * cell],
        [(ax - 16) * cell, (ay - 14) * cell]]})

    # six mobility hubs spread over the core saturate the hub sub-score
    hubs = []
    for dx, dy in [(0, 0), (12, 0), (-12, 0), (0, 12), (0, -12), (10, 10)]:
        hx, hy = ax + dx, ay + dy
        if 0 <= hx < planner.w and 0 <= hy < planner.h:
            hubs.append({"x": (hx + 0.5) * cell, "y": (hy + 0.5) * cell})
    # a station beside every residential ward
    for dx, dy in ward_offsets:
        sx, sy = ax + dx, ay + dy
        if 0 <= sx < planner.w and 0 <= sy < planner.h:
            stations.append({"type": "subway", "x": (sx + 0.5) * cell, "y": (sy + 0.5) * cell})

    return {
        "zones": zones,
        "facilities": facilities,
        "transit": transit,
        "stations": stations,
        "hubs": hubs,
        "metadata": {"generator": "make_elite.py", "objective": objective, "tier": "elite"},
    }


def main():
    if len(sys.argv) < 3:
        print("usage: python make_elite.py terrain.json submission_elite.json")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        terrain = json.load(f)
    submission = generate_elite_submission(terrain)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(submission, f, ensure_ascii=False, indent=2)
    result = S.run(terrain, submission)
    print(result["status"], result.get("score"), result.get("grade"),
          "| base", result.get("base_1000"), "fit", result.get("fit_bonus"),
          "ev", result.get("event_score"))
    if result["status"] != "OK":
        print(result.get("reasons", []))


if __name__ == "__main__":
    main()
