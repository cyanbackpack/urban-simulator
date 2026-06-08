"""Calibration regression: the reference (baseline) pool must stay inside the
published target envelope across multiple seeds -- no hard-gate failures, no S,
A not too common, and a bounded per-terrain spread.
"""

import unittest

import balance_multiseed as B


class BaselineEnvelope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = B.sweep(B.DEFAULT_SEEDS)
        cls.info = B.analyse(cls.rows)

    def test_all_cases_pass_gates(self):
        self.assertEqual(self.info["failed"], 0,
                         f"baseline hard-gate failures: {self.info['fail_cases']}")

    def test_within_published_envelope(self):
        ok, violations = B.check(self.info)
        self.assertTrue(ok, "baseline outside target envelope: " + "; ".join(violations))

    def test_baseline_never_reaches_S(self):
        self.assertEqual(self.info["grades"]["S"], 0,
                         "baseline reference plans should never reach S")


if __name__ == "__main__":
    unittest.main()
