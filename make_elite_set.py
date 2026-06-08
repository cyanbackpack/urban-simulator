#!/usr/bin/env python3
"""Generate the public model-answer set: 5 terrains x 5 objectives = 25 elite
submissions, each scored, written to submissions_elite/.

Because a terrain's rows/events/targets/budget/difficulty do not depend on the
objective (only the `objective` metadata field does), we reuse the five
committed terrain files and override the objective for each of the five briefs.

    python make_elite_set.py            # write set + print grade matrix
    python make_elite_set.py --check    # also fail if any case is below A
"""

import argparse
import csv
import json
import os
import sys

import make_elite
import make_reference
import score_v2 as S

TERRAIN_FILES = {
    "lake_core": "terrain_lake_core.json",
    "twin_coast": "terrain_twin_coast.json",
    "mountain_gate": "terrain_mountain_gate.json",
    "great_delta": "terrain_great_delta.json",
    "central_plain": "terrain_central_plain.json",
}
OBJECTIVES = [
    "Financial Capital",
    "Logistics Hub",
    "Innovation City",
    "Tourism Capital",
    "Eco Metropolis",
]
OUT_DIR = "submissions_elite"
REF_DIR = "submissions_reference"


def slug(name):
    return name.lower().replace(" ", "_")


def build_set(write=True):
    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        os.makedirs(REF_DIR, exist_ok=True)
    rows = []
    for tkey, tfile in TERRAIN_FILES.items():
        with open(tfile, encoding="utf-8") as f:
            base = json.load(f)
        for obj in OBJECTIVES:
            terrain = dict(base)
            terrain["objective"] = obj
            elite = make_elite.generate_elite_submission(terrain)
            ref = make_reference.generate_reference_submission(terrain)
            er = S.run(terrain, elite)
            rr = S.run(terrain, ref)
            name = f"{tkey}_{slug(obj)}"
            if write:
                with open(os.path.join(OUT_DIR, f"elite_{name}.json"), "w", encoding="utf-8") as f:
                    json.dump(elite, f, ensure_ascii=False, indent=2)
                with open(os.path.join(REF_DIR, f"reference_{name}.json"), "w", encoding="utf-8") as f:
                    json.dump(ref, f, ensure_ascii=False, indent=2)
            rows.append({
                "terrain": tkey, "objective": obj,
                "elite_score": er.get("score", 0), "elite_grade": er.get("grade", "D"),
                "elite_status": er["status"],
                "ref_score": rr.get("score", 0), "ref_grade": rr.get("grade", "D"),
                "ref_status": rr["status"],
            })
    return rows


def print_matrix(rows):
    by = {(r["terrain"], r["objective"]): r for r in rows}
    head = "terrain".ljust(15) + "".join(o[:9].ljust(11) for o in OBJECTIVES)
    print("ELITE (model answers)")
    print(head)
    for tkey in TERRAIN_FILES:
        line = tkey.ljust(15)
        for obj in OBJECTIVES:
            r = by[(tkey, obj)]
            line += f"{r['elite_grade']}{r['elite_score']:>6.0f}".ljust(11)
        print(line)
    print("\nBASELINE (reference) for comparison")
    print(head)
    for tkey in TERRAIN_FILES:
        line = tkey.ljust(15)
        for obj in OBJECTIVES:
            r = by[(tkey, obj)]
            line += f"{r['ref_grade']}{r['ref_score']:>6.0f}".ljust(11)
        print(line)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="exit 1 if any elite case is below A or any case fails")
    ap.add_argument("--no-write", action="store_true", help="do not write JSON files")
    args = ap.parse_args()

    rows = build_set(write=not args.no_write)
    print_matrix(rows)

    from collections import Counter
    eg = Counter(r["elite_grade"] for r in rows)
    rg = Counter(r["ref_grade"] for r in rows)
    n_s = sum(1 for r in rows if r["elite_grade"] == "S")
    print(f"\nelite grades   {dict(sorted(eg.items()))}  (S proven in {n_s}/25)")
    print(f"baseline grades {dict(sorted(rg.items()))}")

    if not args.no_write:
        with open("elite_set_report.csv", "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            wr.writeheader()
            wr.writerows(rows)
        print(f"\nwrote {OUT_DIR}/ ({len(rows)} elite), {REF_DIR}/ ({len(rows)} reference), elite_set_report.csv")

    if args.check:
        bad = [r for r in rows if r["elite_status"] != "OK" or r["elite_grade"] in ("B", "C", "D")]
        if bad:
            print("\nFAIL: elite cases below A:")
            for r in bad:
                print(f"  {r['terrain']}/{r['objective']}: {r['elite_grade']} {r['elite_score']} ({r['elite_status']})")
            sys.exit(1)
        print("\nOK: every elite case is A or better.")
    sys.exit(0)


if __name__ == "__main__":
    main()
