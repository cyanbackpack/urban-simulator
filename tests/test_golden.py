"""Golden-score regression: the saved model-answer submissions must keep
scoring the same against their terrains. Catches accidental scorer drift.

The golden values live in tests/golden_scores.json. Regenerate them
deliberately (and review the diff) only when a scoring change is intended:

    python -m tests.regen_golden
"""

import json
import os
import unittest

import score_v2 as S
import webapp

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOL = 0.5  # points; deterministic, so this only absorbs float formatting noise


def _load(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return json.load(f)


class GoldenScores(unittest.TestCase):
    def test_saved_submissions_match_golden(self):
        golden = _load(os.path.join("tests", "golden_scores.json"))
        self.assertTrue(golden, "golden file is empty")
        terrains = {}
        for rel, exp in golden.items():
            tkey, obj = webapp.parse_set_name(rel)
            self.assertIsNotNone(tkey, f"could not map terrain for {rel}")
            self.assertIsNotNone(obj, f"could not map objective for {rel}")
            if tkey not in terrains:
                terrains[tkey] = _load(webapp.TERRAIN_KEYS[tkey])
            terrain = dict(terrains[tkey]); terrain["objective"] = obj
            r = S.run(terrain, _load(rel))
            self.assertEqual(r["status"], exp["status"], f"{rel} status changed")
            self.assertEqual(r["grade"], exp["grade"],
                             f"{rel} grade {r['grade']} != golden {exp['grade']} "
                             f"(score {r['score']} vs {exp['score']})")
            self.assertAlmostEqual(r["score"], exp["score"], delta=TOL,
                                   msg=f"{rel} score {r['score']} drifted from golden {exp['score']}")


if __name__ == "__main__":
    unittest.main()
