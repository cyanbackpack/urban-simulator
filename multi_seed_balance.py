#!/usr/bin/env python3
"""Run baseline balance sweeps across multiple seeds.

    python multi_seed_balance.py balance_multi_seed.csv balance_multi_seed_summary.md 1 2 7 11
"""

import csv
import sys
from collections import Counter, defaultdict

import balance_test


DEFAULT_SEEDS = [1, 2, 7, 11]
GRADE_ORDER = ["S", "A", "B", "C", "D"]


def run(seeds):
    rows = []
    for seed in seeds:
        for row in balance_test.run(seed):
            out = dict(row)
            out["seed"] = seed
            rows.append(out)
    return rows


def write_csv(rows, out_path):
    fields = ["seed", "terrain_key", "terrain", "objective", "status", "score", "grade",
              *balance_test.AXES, "base_1000", "fit_bonus", "event_score", "difficulty",
              "spent", "budget", "reasons"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def grade_counts(rows):
    counts = Counter(row["grade"] for row in rows)
    return " ".join(f"{grade} {counts.get(grade, 0)}" for grade in GRADE_ORDER if counts.get(grade, 0))


def summarize(rows, seeds):
    by_seed = defaultdict(list)
    by_case = defaultdict(list)
    for row in rows:
        by_seed[int(row["seed"])].append(row)
        by_case[(row["terrain_key"], row["objective"])].append(float(row["score"]))

    ok = [row for row in rows if row["status"] == "OK"]
    scores = [float(row["score"]) for row in ok]
    lines = [
        "# Multi-Seed Calibration Report",
        "",
        f"Seeds: {', '.join(str(seed) for seed in seeds)}",
        f"Cases: {len(rows)}",
        f"OK: {len(ok)}",
        f"Failed: {len(rows) - len(ok)}",
        f"Average OK score: {sum(scores) / len(scores):.1f}" if scores else "Average OK score: n/a",
        f"Score range: {min(scores):.1f} - {max(scores):.1f}" if scores else "Score range: n/a",
        f"Grade spread: {grade_counts(rows)}",
        "",
        "## By Seed",
        "",
        "| seed | ok | avg | min | max | grades |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for seed in seeds:
        seed_rows = by_seed[seed]
        seed_ok = [row for row in seed_rows if row["status"] == "OK"]
        seed_scores = [float(row["score"]) for row in seed_ok]
        avg = sum(seed_scores) / len(seed_scores) if seed_scores else 0
        lo = min(seed_scores) if seed_scores else 0
        hi = max(seed_scores) if seed_scores else 0
        lines.append(f"| {seed} | {len(seed_ok)}/{len(seed_rows)} | {avg:.1f} | {lo:.1f} | {hi:.1f} | {grade_counts(seed_rows)} |")

    unstable = []
    for (terrain, objective), case_scores in by_case.items():
        spread = max(case_scores) - min(case_scores)
        unstable.append((spread, terrain, objective, min(case_scores), max(case_scores)))
    unstable.sort(reverse=True)

    lines += [
        "",
        "## Largest Seed Sensitivity",
        "",
        "| spread | terrain | objective | min | max |",
        "| ---: | --- | --- | ---: | ---: |",
    ]
    for spread, terrain, objective, lo, hi in unstable[:10]:
        lines.append(f"| {spread:.1f} | {terrain} | {objective} | {lo:.1f} | {hi:.1f} |")

    failed = [row for row in rows if row["status"] != "OK"]
    if failed:
        lines += ["", "## Failed Cases", ""]
        for row in failed:
            lines.append(f"- seed {row['seed']} {row['terrain_key']} / {row['objective']}: {row['reasons']}")

    return "\n".join(lines) + "\n"


def write_markdown(rows, seeds, out_path):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(summarize(rows, seeds))


def main():
    out_csv = sys.argv[1] if len(sys.argv) > 1 else "balance_multi_seed.csv"
    out_md = sys.argv[2] if len(sys.argv) > 2 else "balance_multi_seed_summary.md"
    seeds = [int(value) for value in sys.argv[3:]] if len(sys.argv) > 3 else DEFAULT_SEEDS
    rows = run(seeds)
    write_csv(rows, out_csv)
    write_markdown(rows, seeds, out_md)
    print(summarize(rows, seeds))
    print(f"wrote {out_csv} and {out_md}")
    failed = [row for row in rows if row["status"] != "OK"]
    sys.exit(0 if not failed else 2)


if __name__ == "__main__":
    main()
