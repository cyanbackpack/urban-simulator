"""Model-answer guarantees: every elite case on the committed terrains reaches
at least A, and S is provably achievable (the headroom above the baseline is
real). Also asserts the elite pool dominates the baseline pool everywhere.
"""

import unittest

import make_elite_set as M


class EliteSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = M.build_set(write=False)

    def test_every_elite_case_is_A_or_better(self):
        bad = [r for r in self.rows
               if r["elite_status"] != "OK" or r["elite_grade"] in ("B", "C", "D")]
        self.assertEqual(bad, [], "elite cases below A: " +
                         ", ".join(f"{r['terrain']}/{r['objective']}={r['elite_grade']}" for r in bad))

    def test_S_is_achievable(self):
        n_s = sum(1 for r in self.rows if r["elite_grade"] == "S")
        self.assertGreaterEqual(n_s, 3, f"expected several S-grade exemplars, got {n_s}")

    def test_elite_beats_baseline_everywhere(self):
        worse = [r for r in self.rows if r["elite_score"] < r["ref_score"]]
        self.assertEqual(worse, [], "elite scored below baseline on: " +
                         ", ".join(f"{r['terrain']}/{r['objective']}" for r in worse))


if __name__ == "__main__":
    unittest.main()
