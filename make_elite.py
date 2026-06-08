#!/usr/bin/env python3
"""Generate a stronger event-aware reference submission.

This is intentionally transparent and deterministic: start from
`make_reference.py`, then add small event-targeted zones/facilities/transit
that a coding agent can inspect, edit, and improve.

    python make_elite.py terrain_twin_coast.json submissions_elite/elite_twin_coast_logistics.json
"""

import json
import sys
from pathlib import Path

import geometry as G
import make_reference
import score_v2 as S


def event_by_type(terrain, etype):
    for event in terrain.get("events", []):
        if event.get("type") == etype:
            return event
    return None


def event_cell(terrain, event):
    cell = terrain["cell_size_m"]
    return int(event["x"] // cell), int(event["y"] // cell)


def mark_existing(planner, submission):
    for zone in submission.get("zones", []):
        for x, y in G.fill_polygon(zone.get("polygon", []), planner.cell, planner.w, planner.h):
            planner.occupied[y, x] = True


def add_facility_once(submission, ftype, x, y):
    for facility in submission.get("facilities", []):
        if facility.get("type") == ftype and abs(facility.get("x", 0) - x) < 1 and abs(facility.get("y", 0) - y) < 1:
            return
    submission.setdefault("facilities", []).append({"type": ftype, "x": x, "y": y})


def add_event_zone(planner, submission, terrain, etype, use, hw, hh, bias=(0, 0)):
    event = event_by_type(terrain, etype)
    if not event:
        return None
    x, y = event_cell(terrain, event)
    prefer_open = use not in ("PARK", "GREENBELT")
    return planner.add_zone(
        submission.setdefault("zones", []),
        use,
        (x + bias[0], y + bias[1]),
        hw,
        hh,
        prefer_open=prefer_open,
    )


def add_event_facility(planner, submission, terrain, etype, ftype):
    event = event_by_type(terrain, etype)
    if not event:
        return
    x, y = planner.meters(planner.find_point(event_cell(terrain, event)))
    add_facility_once(submission, ftype, x, y)


def add_freight_synergy(submission, terrain):
    mineral = event_by_type(terrain, "mineral_deposit")
    harbor = event_by_type(terrain, "deep_harbor")
    if not (mineral and harbor):
        return
    mx, my = mineral["x"], mineral["y"]
    hx, hy = harbor["x"], harbor["y"]
    mid = [(mx + hx) / 2, (my + hy) / 2]
    submission.setdefault("transit", []).append({
        "type": "freight_rail",
        "path": [[mx, my], mid, [hx, hy]],
    })
    add_facility_once(submission, "port", hx, hy)
    add_facility_once(submission, "freight_terminal", mx, my)


def improve_submission(terrain, submission):
    planner = make_reference.Planner(terrain)
    mark_existing(planner, submission)

    # Opportunity extraction.
    add_event_zone(planner, submission, terrain, "deep_harbor", "LOGISTICS", 5, 4)
    add_event_zone(planner, submission, terrain, "deep_harbor", "INDUSTRIAL", 4, 4, bias=(6, 0))
    add_event_zone(planner, submission, terrain, "mineral_deposit", "INDUSTRIAL", 5, 4)
    add_event_zone(planner, submission, terrain, "mineral_deposit", "LOGISTICS", 4, 4, bias=(5, 2))
    add_event_zone(planner, submission, terrain, "oil_field", "INDUSTRIAL", 5, 4)
    add_event_zone(planner, submission, terrain, "oil_field", "LOGISTICS", 4, 4, bias=(5, 2))
    add_event_zone(planner, submission, terrain, "wind_corridor", "PUBLIC", 4, 4)

    # Hazard and mixed-event buffers.
    for etype in ("fault_line", "landslide_zone", "typhoon_corridor", "subsidence_zone", "floodplain", "aquifer_recharge"):
        add_event_zone(planner, submission, terrain, etype, "GREENBELT", 6, 5)
        add_event_zone(planner, submission, terrain, etype, "PARK", 4, 4, bias=(4, 3))

    add_event_facility(planner, submission, terrain, "deep_harbor", "port")
    add_event_facility(planner, submission, terrain, "wind_corridor", "power")
    add_event_facility(planner, submission, terrain, "aquifer_recharge", "water_treatment")
    add_event_facility(planner, submission, terrain, "floodplain", "water_treatment")
    add_freight_synergy(submission, terrain)

    submission.setdefault("metadata", {})["generator"] = "make_elite.py"
    submission["metadata"]["strategy"] = "event-aware deterministic reference"
    return submission


def generate_elite_submission(terrain):
    return improve_submission(terrain, make_reference.generate_reference_submission(terrain))


def main():
    if len(sys.argv) < 3:
        print("usage: python make_elite.py terrain.json submission.json")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        terrain = json.load(f)
    submission = generate_elite_submission(terrain)
    out = Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(submission, f, ensure_ascii=False, indent=2)
    result = S.run(terrain, submission)
    print(result["status"], result.get("score"), result.get("grade"), "events", result.get("event_score"))
    if result["status"] != "OK":
        print(result.get("reasons", []))


if __name__ == "__main__":
    main()
