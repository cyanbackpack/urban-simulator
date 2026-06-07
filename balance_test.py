#!/usr/bin/env python3
"""Run the 5 terrain x 5 objective baseline balance sweep.

    python balance_test.py balance_report.csv 3
"""

import csv
import json
import sys
from collections import Counter

import make_reference
import score_v2 as S
import terrain_gen


TERRAINS = ["lake_core", "twin_coast", "mountain_gate", "great_delta", "central_plain"]
OBJECTIVES = [
    "Financial Capital",
    "Logistics Hub",
    "Innovation City",
    "Tourism Capital",
    "Eco Metropolis",
]
AXES = ["economy", "transport", "environment", "housing", "urban_form"]


def run(seed=3):
    rows = []
    for ttype in TERRAINS:
        for objective in OBJECTIVES:
            terrain = terrain_gen.build(ttype, objective, seed)
            submission = make_reference.generate_reference_submission(terrain)
            result = S.run(terrain, submission)
            row = {
                "terrain_key": ttype,
                "terrain": terrain["terrain_type"],
                "objective": objective,
                "status": result["status"],
                "score": result.get("score", 0),
                "grade": result.get("grade", "D"),
                "base_1000": result.get("base_1000", 0),
                "fit_bonus": result.get("fit_bonus", 0),
                "event_score": result.get("event_score", 0),
                "difficulty": result.get("difficulty", terrain.get("difficulty", 1.0)),
                "spent": result.get("stats", {}).get("spent", 0),
                "budget": result.get("stats", {}).get("budget", terrain.get("budget", 0)),
                "reasons": "; ".join(result.get("reasons", [])),
            }
            for axis in AXES:
                row[axis] = result.get("axes", {}).get(axis, 0)
            rows.append(row)
    return rows


def write_csv(rows, out_path):
    fields = ["terrain_key", "terrain", "objective", "status", "score", "grade", *AXES,
              "base_1000", "fit_bonus", "event_score", "difficulty", "spent", "budget", "reasons"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def summary(rows):
    ok = [r for r in rows if r["status"] == "OK"]
    grades = Counter(r["grade"] for r in rows)
    avg = sum(float(r["score"]) for r in ok) / len(ok) if ok else 0
    failed = [r for r in rows if r["status"] != "OK"]
    return {
        "count": len(rows),
        "ok": len(ok),
        "failed": len(failed),
        "avg_ok_score": round(avg, 1),
        "grades": dict(sorted(grades.items())),
        "failed_cases": [
            {"terrain": r["terrain_key"], "objective": r["objective"], "reasons": r["reasons"]}
            for r in failed
        ],
    }


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "balance_report.csv"
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    rows = run(seed)
    write_csv(rows, out)
    info = summary(rows)
    print(json.dumps(info, indent=2, ensure_ascii=False))
    print(f"wrote {out}")
    sys.exit(0 if info["failed"] == 0 else 2)


if __name__ == "__main__":
    main()
