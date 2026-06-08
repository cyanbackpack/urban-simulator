"""Regenerate tests/golden_scores.json from the saved model-answer sets.

Run this deliberately after an intended scoring change and review the diff:

    python -m tests.regen_golden
"""

import glob
import json
import os

import score_v2 as S
import webapp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    golden = {}
    for d in ("submissions_elite", "submissions_reference"):
        for p in sorted(glob.glob(os.path.join(ROOT, d, "*.json"))):
            tkey, obj = webapp.parse_set_name(p)
            with open(os.path.join(ROOT, webapp.TERRAIN_KEYS[tkey]), encoding="utf-8") as f:
                terrain = json.load(f)
            terrain = dict(terrain); terrain["objective"] = obj
            with open(p, encoding="utf-8") as f:
                sub = json.load(f)
            r = S.run(terrain, sub)
            rel = os.path.relpath(p, ROOT)
            golden[rel] = {"score": r["score"], "grade": r["grade"], "status": r["status"]}
    out = os.path.join(ROOT, "tests", "golden_scores.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(golden, f, indent=1, sort_keys=True)
    print(f"wrote {len(golden)} entries to {out}")


if __name__ == "__main__":
    main()
