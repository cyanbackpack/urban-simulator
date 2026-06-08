#!/usr/bin/env python3
"""Generate a deterministic baseline/reference submission for a terrain.

The output is intentionally conservative: a connected arterial grid, a compact
central city, enough residents/jobs for the hard gates, and objective-specific
facilities/transit. It is a balance-test baseline, not a polished optimal plan.

    python make_reference.py terrain.json submission_reference.json
"""

import json
import math
import sys

import numpy as np

import score_v2 as S


OBJECTIVES = [
    "Financial Capital",
    "Logistics Hub",
    "Innovation City",
    "Eco Metropolis",
    "Tourism Capital",
]


def rect(cx, cy, hw, hh, cell):
    return [
        [(cx - hw) * cell, (cy - hh) * cell],
        [(cx + hw) * cell, (cy - hh) * cell],
        [(cx + hw) * cell, (cy + hh) * cell],
        [(cx - hw) * cell, (cy + hh) * cell],
    ]


def prefix(mask):
    return np.pad(mask.astype(int), ((1, 0), (1, 0))).cumsum(axis=0).cumsum(axis=1)


def rect_sum(pref, x0, y0, x1, y1):
    return pref[y1, x1] - pref[y0, x1] - pref[y1, x0] + pref[y0, x0]


class Planner:
    def __init__(self, terrain):
        self.t = terrain
        self.cell = terrain["cell_size_m"]
        self.rows = np.array([list(r) for r in terrain["rows"]])
        self.h, self.w = self.rows.shape
        self.buildable = ~np.isin(self.rows, list(S.NON_BUILDABLE))
        self.sensitive = np.isin(self.rows, ["T", "w"])
        self.openish = np.isin(self.rows, [".", "F"])
        self.occupied = np.zeros_like(self.buildable, dtype=bool)
        self.build_pref = prefix(self.buildable)
        self.sens_pref = prefix(self.sensitive)
        self.open_pref = prefix(self.openish)

    def occupied_pref(self):
        return prefix(self.occupied)

    def find_rect(self, desired, hw, hh, prefer_open=True):
        occ_pref = self.occupied_pref()
        area = (hw * 2) * (hh * 2)
        best = None
        dx0, dy0 = desired
        for cy in range(hh, self.h - hh):
            y0, y1 = cy - hh, cy + hh
            for cx in range(hw, self.w - hw):
                x0, x1 = cx - hw, cx + hw
                if rect_sum(self.build_pref, x0, y0, x1, y1) != area:
                    continue
                if rect_sum(occ_pref, x0, y0, x1, y1):
                    continue
                sens = rect_sum(self.sens_pref, x0, y0, x1, y1)
                open_cells = rect_sum(self.open_pref, x0, y0, x1, y1)
                dist = (cx - dx0) ** 2 + (cy - dy0) ** 2
                score = dist + sens * 95
                if prefer_open:
                    score += (area - open_cells) * 35
                if best is None or score < best[0]:
                    best = (score, cx, cy)
        if best is None:
            return None
        _, cx, cy = best
        self.occupied[cy - hh:cy + hh, cx - hw:cx + hw] = True
        return cx, cy

    def find_point(self, desired):
        pt = self.find_rect(desired, 2, 2, prefer_open=False)
        if pt:
            return pt
        ys, xs = np.where(self.buildable)
        if len(xs) == 0:
            return self.w // 2, self.h // 2
        d = (xs - desired[0]) ** 2 + (ys - desired[1]) ** 2
        i = int(np.argmin(d))
        return int(xs[i]), int(ys[i])

    def add_zone(self, zones, use, desired, hw, hh, prefer_open=True):
        pt = self.find_rect(desired, hw, hh, prefer_open=prefer_open)
        if not pt:
            return None
        cx, cy = pt
        zones.append({"use": use, "polygon": rect(cx, cy, hw, hh, self.cell)})
        return pt

    def meters(self, cell_xy):
        cx, cy = cell_xy
        return (cx + 0.5) * self.cell, (cy + 0.5) * self.cell


def objective_specs(objective):
    specs = [
        ("CBD", (0, 0), 5, 5),
        ("COMMERCIAL", (-12, 0), 6, 4),
        ("RES_HIGH", (14, 0), 7, 7),
        ("RES_HIGH", (2, 16), 7, 7),
        ("RES_MED", (-20, 12), 9, 8),
        ("RES_MED", (-26, -8), 9, 8),
        ("RES_LOW", (24, 16), 9, 7),
        ("PARK", (0, -14), 5, 5),
        ("PARK", (22, -12), 5, 5),
        ("PUBLIC", (-4, 24), 4, 4),
    ]

    if objective == "Financial Capital":
        specs += [
            ("CBD", (10, -10), 4, 4),
            ("COMMERCIAL", (-4, -14), 6, 4),
            ("PARK", (15, 12), 4, 4),
        ]
    elif objective == "Logistics Hub":
        specs += [
            ("INDUSTRIAL", (28, 0), 7, 6),
            ("LOGISTICS", (38, 8), 6, 5),
            ("LOGISTICS", (30, -12), 5, 5),
        ]
    elif objective == "Innovation City":
        specs += [
            ("UNIVERSITY", (-10, -16), 6, 5),
            ("MEDICAL", (8, -16), 5, 5),
            ("PUBLIC", (-18, -16), 4, 4),
            ("PARK", (-2, -24), 5, 5),
        ]
    elif objective == "Eco Metropolis":
        specs += [
            ("GREENBELT", (-24, -20), 8, 6),
            ("GREENBELT", (28, -20), 8, 6),
            ("PARK", (-12, 24), 6, 5),
            ("RES_MED", (24, 24), 7, 7),
        ]
    elif objective == "Tourism Capital":
        specs += [
            ("PARK", (-8, -22), 7, 5),
            ("PUBLIC", (12, -18), 5, 4),
            ("RES_LOW", (30, -6), 8, 6),
            ("COMMERCIAL", (-16, -14), 5, 4),
        ]
    return specs


def build_transit(t, anchor, objective):
    cell = t["cell_size_m"]
    w, h = t["width"], t["height"]
    ax, ay = anchor
    transit = []

    # Dense arterial mesh keeps the hard connectivity gate boring on purpose.
    xs = list(range(6, w, 8))
    ys = list(range(6, h, 8))
    # Hug the far edges so zones placed in the outermost cells stay reachable.
    if xs and xs[-1] < w - 3:
        xs.append(w - 3)
    if ys and ys[-1] < h - 3:
        ys.append(h - 3)
    for x in xs:
        transit.append({"type": "arterial", "path": [[x * cell, 0], [x * cell, (h - 1) * cell]]})
    for y in ys:
        transit.append({"type": "arterial", "path": [[0, y * cell], [(w - 1) * cell, y * cell]]})

    transit.append({"type": "highway", "path": [[2 * cell, ay * cell], [(w - 2) * cell, ay * cell]]})
    transit.append({"type": "subway", "path": [[(ax - 34) * cell, ay * cell], [ax * cell, ay * cell], [(ax + 34) * cell, (ay - 6) * cell]]})
    transit.append({"type": "subway", "path": [[ax * cell, (ay - 28) * cell], [ax * cell, ay * cell], [ax * cell, (ay + 28) * cell]]})

    if objective == "Logistics Hub":
        transit.append({"type": "freight_rail", "path": [[2 * cell, (ay + 16) * cell], [ax * cell, (ay + 10) * cell], [(w - 2) * cell, (ay + 16) * cell]]})
        transit.append({"type": "rail", "path": [[8 * cell, (ay - 22) * cell], [ax * cell, (ay - 10) * cell], [(w - 8) * cell, (ay - 22) * cell]]})
    elif objective in ("Eco Metropolis", "Tourism Capital"):
        transit.append({"type": "brt", "path": [[(ax - 30) * cell, (ay + 18) * cell], [ax * cell, ay * cell], [(ax + 30) * cell, (ay + 18) * cell]]})
    else:
        transit.append({"type": "rail", "path": [[8 * cell, (ay + 22) * cell], [ax * cell, (ay + 10) * cell], [(w - 8) * cell, (ay + 22) * cell]]})

    stations = []
    for x, y in [(ax - 28, ay), (ax - 14, ay), (ax, ay), (ax + 16, ay - 3), (ax + 30, ay - 6), (ax, ay - 20), (ax, ay + 20)]:
        if 0 <= x < w and 0 <= y < h:
            stations.append({"type": "subway", "x": (x + 0.5) * cell, "y": (y + 0.5) * cell})

    hubs = [
        {"x": (ax + 0.5) * cell, "y": (ay + 0.5) * cell},
        {"x": (ax + 28.5) * cell, "y": (ay + 8.5) * cell},
    ]
    return transit, stations, hubs


def event_point(t, etype):
    for event in t.get("events", []):
        if event["type"] == etype:
            return event["x"], event["y"]
    return None


def build_facilities(planner, anchor, objective):
    t = planner.t
    facilities = []

    def add(ftype, pt):
        x, y = pt
        facilities.append({"type": ftype, "x": x, "y": y})

    ax, ay = anchor
    if objective in ("Financial Capital", "Tourism Capital"):
        add("airport", planner.meters(planner.find_point((max(8, ax - 70), max(8, ay - 55)))))

    if objective == "Logistics Hub":
        harbor = event_point(t, "deep_harbor")
        if harbor:
            add("port", harbor)
        add("freight_terminal", planner.meters(planner.find_point((min(planner.w - 8, ax + 42), ay + 8))))
    else:
        harbor = event_point(t, "deep_harbor")
        if harbor and objective == "Tourism Capital":
            add("port", harbor)

    if objective in ("Eco Metropolis", "Innovation City"):
        water = event_point(t, "aquifer_recharge") or event_point(t, "floodplain")
        if water:
            add("water_treatment", water)

    wind = event_point(t, "wind_corridor")
    if wind and objective in ("Eco Metropolis", "Logistics Hub"):
        add("power", wind)
    else:
        add("power", planner.meters(planner.find_point((min(planner.w - 8, ax + 62), min(planner.h - 8, ay + 42)))))

    return facilities


def generate_reference_submission(terrain):
    planner = Planner(terrain)
    objective = terrain.get("objective", "Financial Capital")
    start = planner.find_rect((terrain["width"] // 2, int(terrain["height"] * 0.62)), 5, 5)
    if not start:
        start = (terrain["width"] // 2, terrain["height"] // 2)
    ax, ay = start

    zones = []
    # Reserve the anchor CBD cell region already selected above.
    zones.append({"use": "CBD", "polygon": rect(ax, ay, 5, 5, planner.cell)})
    for use, offset, hw, hh in objective_specs(objective)[1:]:
        dx, dy = offset
        prefer_open = use not in ("PARK", "GREENBELT")
        planner.add_zone(zones, use, (ax + dx, ay + dy), hw, hh, prefer_open=prefer_open)

    transit, stations, hubs = build_transit(terrain, (ax, ay), objective)
    facilities = build_facilities(planner, (ax, ay), objective)
    return {
        "zones": zones,
        "facilities": facilities,
        "transit": transit,
        "stations": stations,
        "hubs": hubs,
        "metadata": {"generator": "make_reference.py", "objective": objective},
    }


def main():
    if len(sys.argv) < 3:
        print("usage: python make_reference.py terrain.json submission.json")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        terrain = json.load(f)
    submission = generate_reference_submission(terrain)
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        json.dump(submission, f, ensure_ascii=False, indent=2)
    result = S.run(terrain, submission)
    print(result["status"], result.get("score"), result.get("grade"), "events", result.get("event_score"))
    if result["status"] != "OK":
        print(result.get("reasons", []))


if __name__ == "__main__":
    main()
