#!/usr/bin/env python3
"""Multi-seed balance sweep for the reference (baseline) pool.

Runs the 5 terrain x 5 objective reference plans across several seeds and
reports the aggregate grade distribution, per-terrain spread, and whether the
result stays inside the published target distribution for the *baseline* pool.

The baseline pool is the floor of the benchmark: competent-but-unoptimised
plans. It should cluster around B, allow some A for the strongest cases, never
reach S (S is reserved for plans that genuinely beat the baseline), and never
hard-fail a gate.

    python balance_multiseed.py            # default seeds, human summary
    python balance_multiseed.py --json     # machine-readable
    python balance_multiseed.py --check    # exit 1 if outside target envelope

Used both as a tuning tool and as a regression check (see tests/).
"""

import argparse
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
DEFAULT_SEEDS = [1, 2, 3, 7, 11]

# Published target envelope for the BASELINE pool (fractions of OK cases).
TARGET = {
    "fail_max": 0.0,        # no hard-gate failures allowed
    "S_max": 0.0,           # baseline never reaches S
    "A_max": 0.30,          # A only for the strongest baseline cases
    "C_max": 0.30,          # not too many C
    "gap_max": 110.0,       # per-terrain mean spread (points)
}


def sweep(seeds):
    rows = []
    for s in seeds:
        for tt in TERRAINS:
            for ob in OBJECTIVES:
                terrain = terrain_gen.build(tt, ob, s)
                sub = make_reference.generate_reference_submission(terrain)
                r = S.run(terrain, sub)
                rows.append({
                    "seed": s, "terrain": tt, "objective": ob,
                    "status": r["status"], "score": r.get("score", 0),
                    "grade": r.get("grade", "D"),
                    "reasons": "; ".join(r.get("reasons", [])),
                })
    return rows


def analyse(rows):
    ok = [r for r in rows if r["status"] == "OK"]
    fail = [r for r in rows if r["status"] != "OK"]
    grades = Counter(r["grade"] for r in ok)
    per_terrain = {}
    for r in ok:
        per_terrain.setdefault(r["terrain"], []).append(r["score"])
    means = {k: sum(v) / len(v) for k, v in per_terrain.items()}
    gap = (max(means.values()) - min(means.values())) if means else 0.0
    n = len(rows)
    nok = len(ok)
    frac = {g: grades.get(g, 0) / nok for g in "SABCD"} if nok else {}
    return {
        "cases": n,
        "ok": nok,
        "failed": len(fail),
        "avg_score": round(sum(r["score"] for r in ok) / nok, 1) if nok else 0,
        "grades": {g: grades.get(g, 0) for g in "SABCD"},
        "grade_frac": {g: round(frac.get(g, 0), 3) for g in "SABCD"},
        "per_terrain_mean": {k: round(v, 1) for k, v in sorted(means.items(), key=lambda kv: kv[1])},
        "terrain_gap": round(gap, 1),
        "fail_cases": [
            {"seed": r["seed"], "terrain": r["terrain"], "objective": r["objective"], "reasons": r["reasons"]}
            for r in fail
        ],
    }


def check(info):
    """Return (ok, list-of-violations) against the target envelope."""
    v = []
    if info["failed"] > 0:
        v.append(f"{info['failed']} hard-gate failure(s) (target 0)")
    f = info["grade_frac"]
    if f.get("S", 0) > TARGET["S_max"]:
        v.append(f"S fraction {f['S']:.2f} > {TARGET['S_max']:.2f}")
    if f.get("A", 0) > TARGET["A_max"]:
        v.append(f"A fraction {f['A']:.2f} > {TARGET['A_max']:.2f}")
    if f.get("C", 0) > TARGET["C_max"]:
        v.append(f"C fraction {f['C']:.2f} > {TARGET['C_max']:.2f}")
    if info["terrain_gap"] > TARGET["gap_max"]:
        v.append(f"terrain gap {info['terrain_gap']} > {TARGET['gap_max']}")
    return (not v), v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, nargs="+", default=DEFAULT_SEEDS)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--check", action="store_true", help="exit 1 if outside target envelope")
    args = ap.parse_args()

    rows = sweep(args.seeds)
    info = analyse(rows)
    ok, violations = check(info)

    if args.json:
        print(json.dumps({**info, "within_target": ok, "violations": violations}, ensure_ascii=False, indent=2))
    else:
        print(f"seeds={args.seeds}  cases={info['cases']}  OK={info['ok']}  FAIL={info['failed']}")
        print(f"avg={info['avg_score']}  grades={info['grades']}  ({info['grade_frac']})")
        print(f"terrain gap={info['terrain_gap']}  per-terrain mean={info['per_terrain_mean']}")
        if info["fail_cases"]:
            print("FAILURES:")
            for fc in info["fail_cases"]:
                print(f"  seed {fc['seed']} {fc['terrain']}/{fc['objective']}: {fc['reasons']}")
        print("within target envelope" if ok else "OUTSIDE target: " + "; ".join(violations))

    if args.check and not ok:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
