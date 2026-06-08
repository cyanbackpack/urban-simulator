"""Schema validation: every committed submission is structurally valid, and the
validator rejects common malformations.
"""

import glob
import json
import os
import unittest

import schema

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SchemaValidation(unittest.TestCase):
    def test_committed_submissions_are_valid(self):
        paths = []
        for d in ("submissions_elite", "submissions_reference", "submissions_demo"):
            paths += glob.glob(os.path.join(ROOT, d, "*.json"))
        self.assertTrue(paths, "no committed submissions found")
        for p in paths:
            with open(p, encoding="utf-8") as f:
                sub = json.load(f)
            errs = schema.validate_submission(sub)
            self.assertEqual(errs, [], f"{os.path.basename(p)} failed schema: {errs}")

    def test_rejects_bad_zone_use(self):
        errs = schema.validate_submission({"zones": [{"use": "NOPE", "polygon": [[0, 0], [1, 0], [1, 1]]}]})
        self.assertTrue(any("use" in e for e in errs))

    def test_rejects_short_polygon(self):
        errs = schema.validate_submission({"zones": [{"use": "CBD", "polygon": [[0, 0], [1, 1]]}]})
        self.assertTrue(any("polygon" in e for e in errs))

    def test_rejects_nonnumeric_facility(self):
        errs = schema.validate_submission({"facilities": [{"type": "airport", "x": "a", "y": 1}]})
        self.assertTrue(any("x and y" in e for e in errs))

    def test_accepts_minimal_valid(self):
        errs = schema.validate_submission({
            "zones": [{"use": "CBD", "polygon": [[0, 0], [100, 0], [100, 100]]}],
            "facilities": [{"type": "airport", "x": 10, "y": 10}],
            "transit": [{"type": "subway", "path": [[0, 0], [100, 100]]}],
            "stations": [{"type": "subway", "x": 5, "y": 5}],
            "hubs": [{"x": 5, "y": 5}],
        })
        self.assertEqual(errs, [])


if __name__ == "__main__":
    unittest.main()
