#!/usr/bin/env python3
"""Validate a CityBench submission against hard gates and key constraints.

    python validate.py terrain.json submission.json
"""

import json
import sys

import score_v2 as S


def non_buildable_conflicts(R, limit=12):
    out = []
    for y in range(R["h"]):
        for x in range(R["w"]):
            use = R["use"][y][x]
            if use and R["land"][y][x] in S.NON_BUILDABLE:
                out.append({"cell": [x, y], "terrain": R["land"][y][x], "use": use})
                if len(out) >= limit:
                    return out
    return out


def unreachable_development(R, limit=12):
    near = S.near_network_grid(R)
    out = []
    for y in range(R["h"]):
        for x in range(R["w"]):
            use = R["use"][y][x]
            if use in S.ZONES and not S.ZONES[use].get("green") and not near[y][x]:
                out.append({"cell": [x, y], "use": use})
                if len(out) >= limit:
                    return out
    return out


def validate(terrain, submission):
    R = S.rasterize(terrain, submission)
    reasons, cost = S.gates(terrain, submission, R)
    res, jobs = S.totals(R)
    comps = S.net_components(R["net"], R["w"], R["h"])
    score = S.run(terrain, submission)
    return {
        "status": "OK" if not reasons else "FAILED",
        "score_status": score["status"],
        "score": score.get("score", 0),
        "grade": score.get("grade", "D"),
        "reasons": reasons,
        "budget": {"spent": int(cost), "limit": terrain["budget"], "ok": cost <= terrain["budget"]},
        "capacity": {
            "residents": int(res),
            "resident_min": int(0.4 * terrain["targets"]["residents"]),
            "jobs": int(jobs),
            "job_min": int(0.4 * terrain["targets"]["jobs"]),
        },
        "network": {
            "components": comps,
            "largest_share": round(max(comps) / sum(comps), 3) if comps else 0,
        },
        "samples": {
            "non_buildable_conflicts": non_buildable_conflicts(R),
            "unreachable_development": unreachable_development(R),
        },
        "events": terrain.get("events", []),
    }


def main():
    if len(sys.argv) != 3:
        print("usage: python validate.py terrain.json submission.json")
        sys.exit(1)
    with open(sys.argv[1], encoding="utf-8") as f:
        terrain = json.load(f)
    with open(sys.argv[2], encoding="utf-8") as f:
        submission = json.load(f)
    result = validate(terrain, submission)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["status"] == "OK" else 2)


if __name__ == "__main__":
    main()
