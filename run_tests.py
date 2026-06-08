#!/usr/bin/env python3
"""Local regression runner (no third-party deps beyond numpy for the
generators). Runs the same suite CI runs.

    python run_tests.py          # full suite
    python run_tests.py -q       # quieter

Individual checks can also be run directly, e.g.:
    python balance_multiseed.py --check
    python make_elite_set.py --check --no-write
    python schema.py submission.json
"""

import sys
import unittest

ROOT = "tests"


def main():
    verbosity = 1 if "-q" in sys.argv else 2
    loader = unittest.TestLoader()
    suite = loader.discover(ROOT, pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
