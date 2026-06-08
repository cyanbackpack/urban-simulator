#!/usr/bin/env python3
"""Lightweight, dependency-free schema validation for CityBench submissions.

This is a *structural* check (shapes and types), separate from score_v2's
hard-gate rules (budget / connectivity / land use). It exists so the web UI,
the test suite, and participants can fail fast on malformed JSON with a clear
message instead of a deep stack trace inside the scorer.

    from schema import validate_submission
    errors = validate_submission(sub)   # -> list[str]; empty means valid

    python schema.py submission.json    # CLI: print errors, exit 1 if invalid
"""

import json
import sys

import score_v2 as S

VALID_USES = set(S.ZONES.keys())
VALID_FACILITIES = set(S.FACILITY_COST.keys())
VALID_TRANSIT = set(S.TRANSIT.keys())


def _is_point(p):
    return (isinstance(p, (list, tuple)) and len(p) == 2
            and all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in p))


def validate_submission(sub):
    """Return a list of human-readable problems. Empty list == valid."""
    errors = []
    if not isinstance(sub, dict):
        return ["submission must be a JSON object"]

    zones = sub.get("zones", [])
    if not isinstance(zones, list):
        errors.append("'zones' must be a list")
    else:
        for i, z in enumerate(zones):
            if not isinstance(z, dict):
                errors.append(f"zones[{i}] must be an object"); continue
            use = z.get("use")
            if use not in VALID_USES:
                errors.append(f"zones[{i}].use '{use}' not one of {sorted(VALID_USES)}")
            poly = z.get("polygon")
            if not isinstance(poly, list) or len(poly) < 3:
                errors.append(f"zones[{i}].polygon must be a list of >=3 points")
            elif not all(_is_point(p) for p in poly):
                errors.append(f"zones[{i}].polygon has a malformed point")

    facilities = sub.get("facilities", [])
    if not isinstance(facilities, list):
        errors.append("'facilities' must be a list")
    else:
        for i, f in enumerate(facilities):
            if not isinstance(f, dict):
                errors.append(f"facilities[{i}] must be an object"); continue
            if f.get("type") not in VALID_FACILITIES:
                errors.append(f"facilities[{i}].type '{f.get('type')}' not one of {sorted(VALID_FACILITIES)}")
            if not _is_point([f.get("x"), f.get("y")]):
                errors.append(f"facilities[{i}] needs numeric x and y")

    transit = sub.get("transit", [])
    if not isinstance(transit, list):
        errors.append("'transit' must be a list")
    else:
        for i, line in enumerate(transit):
            if not isinstance(line, dict):
                errors.append(f"transit[{i}] must be an object"); continue
            if line.get("type") not in VALID_TRANSIT:
                errors.append(f"transit[{i}].type '{line.get('type')}' not one of {sorted(VALID_TRANSIT)}")
            path = line.get("path")
            if not isinstance(path, list) or len(path) < 2:
                errors.append(f"transit[{i}].path must be a list of >=2 points")
            elif not all(_is_point(p) for p in path):
                errors.append(f"transit[{i}].path has a malformed point")

    for key in ("stations", "hubs"):
        items = sub.get(key, [])
        if not isinstance(items, list):
            errors.append(f"'{key}' must be a list"); continue
        for i, s in enumerate(items):
            if not isinstance(s, dict) or not _is_point([s.get("x"), s.get("y")]):
                errors.append(f"{key}[{i}] needs numeric x and y")
    return errors


def main():
    if len(sys.argv) != 2:
        print("usage: python schema.py submission.json"); sys.exit(2)
    with open(sys.argv[1], encoding="utf-8") as f:
        sub = json.load(f)
    errs = validate_submission(sub)
    if errs:
        print(f"INVALID ({len(errs)} problem(s)):")
        for e in errs:
            print(f"  - {e}")
        sys.exit(1)
    print("valid submission")
    sys.exit(0)


if __name__ == "__main__":
    main()
